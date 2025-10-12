import logging
from themoviedb import aioTMDb
import PTN
from config import settings

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

tmdb = aioTMDb(key=settings.TMDB_API_KEY, language="en-US", region="US")


# +++ NEW FUNCTION +++
async def find_tmdb_id_by_imdb_id(imdb_id: str, media_type: str) -> int | None:
    """Finds the TMDb ID for a given IMDb ID using the TMDb API."""
    try:
        find_results = await tmdb.find(imdb_id).by("imdb_id")
        # Stremio uses "series" but our internal type is "tv"
        stremio_type = "tv" if media_type in ["series", "tv"] else "movie"

        if stremio_type == "movie" and find_results.movie_results:
            return find_results.movie_results[0].id
        if stremio_type == "tv" and find_results.tv_results:
            return find_results.tv_results[0].id
    except Exception as e:
        LOGGER.error(f"Could not find TMDb ID for IMDb ID {imdb_id}: {e}")
    return None


def format_tmdb_image(path: str, size: str = "w500") -> str:
    return f"https://image.tmdb.org/t/p/{size}{path}" if path else ""


async def get_logo(tmdb_id: int, media_type: str) -> str | None:
    try:
        if media_type == "movie":
            images = await tmdb.movie(tmdb_id).images()
        else:
            images = await tmdb.tv(tmdb_id).images()

        # Prefer English logos, then logos with no language, then any other
        logos = sorted(images.logos, key=lambda x: (x.iso_639_1 != 'en', x.iso_639_1 is not None))
        if logos:
            return format_tmdb_image(logos[0].file_path, "original")
    except Exception:
        return None
    return None


async def get_metadata(filename: str, file_url: str) -> dict | None:
    try:
        parsed = PTN.parse(filename)
        title, year, quality, season, episode = (
            parsed.get("title"), parsed.get("year"), parsed.get("resolution"),
            parsed.get("season"), parsed.get("episode")
        )

        if not title or not quality:
            LOGGER.warning(f"Skipping '{filename}': Missing title or quality.")
            return None

        if isinstance(season, list) or isinstance(episode, list):
            LOGGER.warning(f"Skipping season pack '{filename}'.")
            return None

        if season and episode:
            search_results = await tmdb.search().tv(query=title)
            if not search_results: return None

            show = await tmdb.tv(search_results[0].id).details()
            ep = await tmdb.episode(show.id, season, episode).details()
            logo = await get_logo(show.id, "tv")

            return {
                "tmdb_id": show.id, "title": show.name,
                "release_year": show.first_air_date.year if show.first_air_date else year,
                "rating": round(show.vote_average, 1), "genres": [g.name for g in show.genres],
                "poster": format_tmdb_image(show.poster_path),
                "backdrop": format_tmdb_image(show.backdrop_path, "original"),
                "logo": logo, "description": show.overview, "media_type": "tv",
                "seasons": [{"season_number": season, "episodes": [
                    {"episode_number": episode, "title": ep.name,
                     "episode_backdrop": format_tmdb_image(ep.still_path, "original")}]}],
                "quality": quality, "url": file_url,
            }
        else:
            search_results = await tmdb.search().movies(query=title, year=year)
            if not search_results: return None

            movie = await tmdb.movie(search_results[0].id).details()
            logo = await get_logo(movie.id, "movie")

            return {
                "tmdb_id": movie.id, "title": movie.title,
                "release_year": movie.release_date.year if movie.release_date else year,
                "rating": round(movie.vote_average, 1), "genres": [g.name for g in movie.genres],
                "poster": format_tmdb_image(movie.poster_path),
                "backdrop": format_tmdb_image(movie.backdrop_path, "original"),
                "logo": logo, "description": movie.overview, "media_type": "movie",
                "quality": quality, "url": file_url,
            }
    except Exception as e:
        LOGGER.error(f"Error fetching metadata for '{filename}': {e}")
        return None
