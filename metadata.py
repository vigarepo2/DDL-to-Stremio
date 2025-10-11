from themoviedb import aioTMDb
from config import settings
import PTN
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

tmdb = aioTMDb(key=settings.TMDB_API_KEY)

def format_tmdb_image(path: str) -> str:
    return f"https://image.tmdb.org/t/p/w500{path}" if path else ""

async def metadata(filename: str, file_url: str) -> dict | None:
    try:
        parsed = PTN.parse(filename)
        title = parsed.get("title")
        year = parsed.get("year")
        quality = parsed.get("resolution")
        season = parsed.get("season")
        episode = parsed.get("episode")

        if not title or not quality:
            LOGGER.warning(f"Skipping '{filename}': Missing title or quality.")
            return None

        if season and episode:
            # It's a TV Show
            search_results = await tmdb.search().tv(query=title, year=year)
            if not search_results:
                return None
            
            show_details = await tmdb.tv(search_results[0].id).details()
            ep_details = await tmdb.episode(show_details.id, season, episode).details()
            
            return {
                "tmdb_id": show_details.id,
                "title": show_details.name,
                "release_year": show_details.first_air_date.year if show_details.first_air_date else year,
                "rating": show_details.vote_average,
                "genres": [g.name for g in show_details.genres],
                "poster": format_tmdb_image(show_details.poster_path),
                "backdrop": format_tmdb_image(show_details.backdrop_path),
                "description": show_details.overview,
                "media_type": "tv",
                "seasons": [{
                    "season_number": season,
                    "episodes": [{
                        "episode_number": episode,
                        "title": ep_details.name,
                        "episode_backdrop": format_tmdb_image(ep_details.still_path),
                    }]
                }],
                "quality": quality,
                "url": file_url,
            }
        else:
            # It's a Movie
            search_results = await tmdb.search().movies(query=title, year=year)
            if not search_results:
                return None
            
            movie_details = await tmdb.movie(search_results[0].id).details()
            
            return {
                "tmdb_id": movie_details.id,
                "title": movie_details.title,
                "release_year": movie_details.release_date.year if movie_details.release_date else year,
                "rating": movie_details.vote_average,
                "genres": [g.name for g in movie_details.genres],
                "poster": format_tmdb_image(movie_details.poster_path),
                "backdrop": format_tmdb_image(movie_details.backdrop_path),
                "description": movie_details.overview,
                "media_type": "movie",
                "quality": quality,
                "url": file_url,
            }

    except Exception as e:
        LOGGER.error(f"Error fetching metadata for '{filename}': {e}")
        return None
