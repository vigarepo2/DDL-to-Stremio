import httpx
import os
from urllib.parse import urlparse, unquote
from typing import Optional
from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from config import settings
from database import db
from metadata import metadata
from aiofiles.os import path as aiopath

app = FastAPI(title="DDL Stremio Addon")
app.add_middleware(SessionMiddleware, secret_key="your-super-secret-key")
templates = Jinja2Templates(directory="templates")

# --- Authentication ---
def is_authenticated(request: Request) -> bool:
    return request.session.get("authenticated", False)

def require_auth(request: Request):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return True

# --- Web UI Routes ---
@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
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
async def root(request: Request, _: bool = Depends(require_auth)):
    return templates.TemplateResponse("add.html", {"request": request})

# --- API for adding links ---
@app.post("/api/add-ddl", response_class=JSONResponse)
async def add_ddl_endpoint(request: Request, _: bool = Depends(require_auth)):
    data = await request.json()
    url = data.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required.")

    try:
        filename = os.path.basename(unquote(urlparse(url).path))
        
        async with httpx.AsyncClient() as client:
            head_resp = await client.head(url, follow_redirects=True, timeout=10)
            head_resp.raise_for_status()
            size_bytes = head_resp.headers.get('content-length', '0')
            size_gb = round(int(size_bytes) / (1024**3), 2)
            size = f"{size_gb} GB"
        
        metadata_info = await metadata(filename, url)
        if not metadata_info:
            return JSONResponse({"message": f"Failed to parse metadata from filename: {filename}"}, status_code=400)
        
        await db.insert_media(metadata_info, size=size, name=filename)
        return JSONResponse({"message": f"Successfully processed and added '{metadata_info['title']}'"}, status_code=200)

    except Exception as e:
        LOGGER.error(f"Error processing DDL {url}: {e}")
        return JSONResponse({"message": f"Error processing link: {str(e)}"}, status_code=500)

# --- Stremio Addon Routes ---
@app.get("/stremio/manifest.json")
async def get_manifest():
    return {
        "id": "community.ddl.stremio", "version": "1.0.0", "name": "DDL Streamer",
        "description": "Stream from your Direct Download Links.", "logo": "https://i.imgur.com/f33tN3G.png",
        "types": ["movie", "series"], "resources": ["catalog", "meta", "stream"],
        "catalogs": [
            {"type": "movie", "id": "ddl_movies", "name": "DDL Movies"},
            {"type": "series", "id": "ddl_series", "name": "DDL Series"}
        ], "idPrefixes": ["ddl-"]
    }

@app.get("/stremio/catalog/{media_type}/{catalog_id}.json")
async def get_catalog(media_type: str, catalog_id: str):
    items = await db.get_all_media(media_type.replace("series", "tv"), 0, 100)
    metas = [{
        "id": f"ddl-{item['tmdb_id']}", "type": media_type, "name": item['title'],
        "poster": item.get('poster'), "year": item.get('release_year')
    } for item in items]
    return {"metas": metas}

@app.get("/stremio/meta/{media_type}/{stremio_id}.json")
async def get_meta(media_type: str, stremio_id: str):
    tmdb_id = int(stremio_id.replace("ddl-", ""))
    item = await db.get_media_by_tmdb_id(media_type.replace("series", "tv"), tmdb_id)
    if not item:
        return {"meta": {}}
    
    meta_obj = {
        "id": stremio_id, "type": media_type, "name": item['title'],
        "poster": item.get('poster'), "background": item.get('backdrop'),
        "description": item.get('description'), "year": item.get('release_year'),
        "imdbRating": item.get('rating'), "genres": item.get('genres')
    }
    
    if media_type == 'series':
        meta_obj['videos'] = [
            {
                "id": f"{stremio_id}:{s['season_number']}:{e['episode_number']}",
                "title": e['title'], "season": s['season_number'], "episode": e['episode_number'],
                "thumbnail": e.get('episode_backdrop')
            }
            for s in item.get('seasons', []) for e in s.get('episodes', [])
        ]
    return {"meta": meta_obj}

@app.get("/stremio/stream/{media_type}/{stremio_id}.json")
async def get_streams(media_type: str, stremio_id: str):
    parts = stremio_id.split(':')
    tmdb_id = int(parts[0].replace("ddl-", ""))
    item = await db.get_media_by_tmdb_id(media_type.replace("series", "tv"), tmdb_id)
    if not item:
        return {"streams": []}

    streams = []
    if media_type == 'movie':
        streams = [{"title": f"{q['quality']}\n💾 {q['size']}", "url": q['url']} for q in item.get('telegram', [])]
    else:
        season_num, episode_num = int(parts[1]), int(parts[2])
        for s in item.get('seasons', []):
            if s['season_number'] == season_num:
                for e in s.get('episodes', []):
                    if e['episode_number'] == episode_num:
                        streams = [{"title": f"{q['quality']}\n💾 {q['size']}", "url": q['url']} for q in e.get('telegram', [])]
                        break
                break
    return {"streams": streams}

# --- Root Redirect ---
@app.get("/", include_in_schema=False)
async def root_redirect(request: Request):
    if is_authenticated(request):
        return RedirectResponse(url="/add-link")
    return RedirectResponse(url="/login")
