import httpx
import os
import hashlib
from urllib.parse import urlparse, unquote
from fastapi import FastAPI, Request, Form, Depends, HTTPException, Body
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from database import db
from metadata import get_metadata, format_tmdb_image
import logging

app = FastAPI(title="DDL Stremio Addon - Premium")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(SessionMiddleware, secret_key="a-super-secret-key-that-you-should-change")
templates = Jinja2Templates(directory="templates")

LOGGER = logging.getLogger(__name__)

# --- Authentication ---
def is_authenticated(request: Request) -> bool:
    return request.session.get("authenticated", False)

def require_auth(request: Request):
    if not is_authenticated(request):
        raise HTTPException(status_code=307, headers={"Location": "/login"})

# --- Web Panel Routes (HTML) ---
@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    if is_authenticated(request): return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def handle_login(request: Request, username: str = Form(...), password: str = Form(...)):
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    if username == settings.ADMIN_USERNAME and password_hash == settings.ADMIN_PASSWORD_HASH:
        request.session["authenticated"] = True
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"}, status_code=400)

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)

@app.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request, _: None = Depends(require_auth)):
    stats = await db.get_stats()
    recent_movies, _ = await db.get_media_list('movie', 1, 5)
    recent_tv, _ = await db.get_media_list('tv', 1, 5)
    recent_items = sorted(recent_movies + recent_tv, key=lambda x: x['updated_on'], reverse=True)[:5]
    return templates.TemplateResponse("dashboard.html", {"request": request, "stats": stats, "recent_items": recent_items})

@app.get("/manage/{media_type}", response_class=HTMLResponse)
async def manage_media_page(request: Request, media_type: str, _: None = Depends(require_auth)):
    if media_type not in ['movie', 'tv']: raise HTTPException(status_code=404, detail="Invalid media type")
    return templates.TemplateResponse("media_management.html", {"request": request, "media_type": media_type})

@app.get("/edit/{media_type}/{tmdb_id}", response_class=HTMLResponse)
async def edit_media_page(request: Request, media_type: str, tmdb_id: int, _: None = Depends(require_auth)):
    if media_type not in ['movie', 'tv']: raise HTTPException(status_code=404, detail="Invalid media type")
    media = await db.get_media_by_tmdb_id(media_type, tmdb_id)
    if not media: raise HTTPException(status_code=404, detail="Media not found")
    return templates.TemplateResponse("media_edit.html", {"request": request, "media": media, "media_type": media_type})

# --- API Routes (JSON) ---
@app.post("/api/add-ddl", response_class=JSONResponse)
async def api_add_ddl(request: Request, _: None = Depends(require_auth)):
    data = await request.json()
    url = data.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required.")
    try:
        filename = os.path.basename(unquote(urlparse(url).path))
        async with httpx.AsyncClient() as client:
            resp = await client.head(url, follow_redirects=True, timeout=10)
            resp.raise_for_status()
            size_bytes = int(resp.headers.get('content-length', '0'))
            size_str = f"{round(size_bytes / (1024**3), 2)} GB" if size_bytes > 0 else "N/A"
        metadata_info = await get_metadata(filename, url)
        if not metadata_info:
            return JSONResponse({"message": f"Failed to get metadata for '{filename}'. Check filename format or TMDb availability."}, status_code=400)
        await db.insert_media(metadata_info, size=size_str, name=filename)
        return JSONResponse({"message": f"Successfully added '{metadata_info['title']}'"}, status_code=200)
    except httpx.HTTPStatusError as e:
        return JSONResponse({"message": f"URL returned an error: {e.response.status_code} Not Found"}, status_code=400)
    except httpx.RequestError:
        return JSONResponse({"message": "Could not connect to the URL. Check the link or network."}, status_code=400)
    except Exception as e:
        LOGGER.error(f"Error processing DDL {url}: {e}", exc_info=True)
        return JSONResponse({"message": "An unexpected server error occurred. Check logs for details."}, status_code=500)

# --- NEW API ENDPOINT FOR FETCHING STREAM DETAILS ---
@app.post("/api/fetch-ddl-details", response_class=JSONResponse)
async def api_fetch_ddl_details(request: Request, _: None = Depends(require_auth)):
    data = await request.json()
    url = data.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required.")
    try:
        filename = os.path.basename(unquote(urlparse(url).path))
        async with httpx.AsyncClient() as client:
            resp = await client.head(url, follow_redirects=True, timeout=10)
            resp.raise_for_status()
            size_bytes = int(resp.headers.get('content-length', '0'))
            size_str = f"{round(size_bytes / (1024**3), 2)} GB" if size_bytes > 0 else "N/A"
        return JSONResponse({"name": filename, "size": size_str})
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail=f"URL returned an error: {e.response.status_code}")
    except httpx.RequestError:
        raise HTTPException(status_code=400, detail="Could not connect to the URL.")
    except Exception as e:
        LOGGER.error(f"Error fetching details for DDL {url}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected server error occurred.")

@app.get("/api/media/{media_type}")
async def api_get_media(media_type: str, page: int = 1, search: str = "", _: None = Depends(require_auth)):
    items, total = await db.get_media_list(media_type, page, 12, search)
    return {"items": items, "total": total, "page": page, "page_size": 12}

@app.put("/api/media/{media_type}/{tmdb_id}")
async def api_update_media(media_type: str, tmdb_id: int, data: dict = Body(...), _: None = Depends(require_auth)):
    success = await db.update_media_details(media_type, tmdb_id, data)
    if not success: raise HTTPException(status_code=404, detail="Failed to update or media not found.")
    return {"message": "Media updated successfully"}

@app.delete("/api/media/{media_type}/{tmdb_id}")
async def api_delete_media(media_type: str, tmdb_id: int, _: None = Depends(require_auth)):
    success = await db.delete_media(media_type, tmdb_id)
    if not success: raise HTTPException(status_code=404, detail="Media not found.")
    return {"message": "Media deleted successfully"}

@app.get("/api/refetch-tmdb/{media_type}/{tmdb_id}")
async def api_refetch_tmdb(media_type: str, tmdb_id: int, _: None = Depends(require_auth)):
    from metadata import get_logo, tmdb
    if media_type == 'movie':
        details = await tmdb.movie(tmdb_id).details()
        logo = await get_logo(tmdb_id, "movie")
        return {"title": details.title, "release_year": details.release_date.year if details.release_date else 0, "rating": round(details.vote_average, 1), "poster": format_tmdb_image(details.poster_path), "backdrop": format_tmdb_image(details.backdrop_path, "original"), "logo": logo, "description": details.overview, "genres": [g.name for g in details.genres]}
    else:
        details = await tmdb.tv(tmdb_id).details()
        logo = await get_logo(tmdb_id, "tv")
        return {"title": details.name, "release_year": details.first_air_date.year if details.first_air_date else 0, "rating": round(details.vote_average, 1), "poster": format_tmdb_image(details.poster_path), "backdrop": format_tmdb_image(details.backdrop_path, "original"), "logo": logo, "description": details.overview, "genres": [g.name for g in details.genres]}

@app.get("/api/images/{media_type}/{tmdb_id}")
async def api_get_images(media_type: str, tmdb_id: int, _: None = Depends(require_auth)):
    from metadata import tmdb
    try:
        images = await (tmdb.movie(tmdb_id) if media_type == 'movie' else tmdb.tv(tmdb_id)).images()
        all_images = images.posters + images.backdrops + images.logos
        languages = sorted(list(set(img.iso_639_1 for img in all_images if img.iso_639_1)))
        return { "posters": [{"path": img.file_path, "lang": img.iso_639_1} for img in images.posters], "backdrops": [{"path": img.file_path, "lang": img.iso_639_1} for img in images.backdrops], "logos": [{"path": img.file_path, "lang": img.iso_639_1} for img in images.logos], "languages": languages }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Stremio Addon Routes ---
@app.get("/stremio/manifest.json")
async def get_manifest():
    return {"id": "community.ddl.streamer.premium", "version": "4.0.0", "name": "DDL Streamer (Premium)", "description": "Stream from your personal DDL library.", "logo": "https://i.imgur.com/f33tN3G.png", "types": ["movie", "series"], "resources": ["catalog", "meta", "stream"], "catalogs": [{"type": "movie", "id": "ddl_movies", "name": "DDL Movies"}, {"type": "series", "id": "ddl_series", "name": "DDL TV Shows"}], "idPrefixes": ["ddl-"]}

@app.get("/stremio/catalog/{media_type}/{catalog_id}.json")
async def get_catalog(media_type: str):
    stremio_type = "tv" if media_type == "series" else "movie"
    items, _ = await db.get_media_list(stremio_type, 1, 100)
    metas = [{"id": f"ddl-{i['tmdb_id']}", "type": media_type, "name": i['title'], "poster": i.get('poster'), "year": i.get('release_year'), "logo": i.get('logo')} for i in items]
    return {"metas": metas}

@app.get("/stremio/meta/{media_type}/{stremio_id}.json")
async def get_meta(media_type: str, stremio_id: str):
    tmdb_id = int(stremio_id.replace("ddl-", ""))
    stremio_type = "tv" if media_type == "series" else "movie"
    item = await db.get_media_by_tmdb_id(stremio_type, tmdb_id)
    if not item: return {"meta": {}}
    meta_obj = {"id": stremio_id, "type": media_type, "name": item['title'], "poster": item.get('poster'), "background": item.get('backdrop'), "logo": item.get('logo'), "description": item.get('description'), "year": item.get('release_year'), "imdbRating": item.get('rating'), "genres": item.get('genres')}
    if media_type == 'series':
        meta_obj['videos'] = [{"id": f"{stremio_id}:{s['season_number']}:{e['episode_number']}", "title": e['title'], "season": s['season_number'], "episode": e['episode_number'], "thumbnail": e.get('episode_backdrop')} for s in sorted(item.get('seasons', []), key=lambda x: x['season_number']) for e in sorted(s.get('episodes', []), key=lambda x: x['episode_number'])]
    return {"meta": meta_obj}

@app.get("/stremio/stream/{media_type}/{stremio_id}.json")
async def get_streams(media_type: str, stremio_id: str):
    parts = stremio_id.split(':'); tmdb_id = int(parts[0].replace("ddl-", ""))
    stremio_type = "tv" if media_type == "series" else "movie"
    item = await db.get_media_by_tmdb_id(stremio_type, tmdb_id)
    if not item: return {"streams": []}
    streams = []
    if media_type == 'movie':
        streams = [{"name": "DDL", "title": f"{q['quality']} - {q['size']}\n{q['name']}", "url": q['url']} for q in item.get('streams', [])]
    else:
        season_num, episode_num = int(parts[1]), int(parts[2])
        for s in item.get('seasons', []):
            if s['season_number'] == season_num:
                for e in s.get('episodes', []):
                    if e['episode_number'] == episode_num:
                        streams = [{"name": "DDL", "title": f"{q['quality']} - {q['size']}\n{q['name']}", "url": q['url']} for q in e.get('streams', [])]; break
                break
    return {"streams": streams}
