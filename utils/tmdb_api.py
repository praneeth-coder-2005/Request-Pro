# utils/tmdb_api.py
import aiohttp
from config import TMDB_API_KEY, TMDB_IMAGE_BASE_URL
import logging

logger = logging.getLogger(__name__)

async def search_movie_tmdb(query: str) -> list:
    """Searches for movies on TMDB."""
    if not TMDB_API_KEY:
        logger.error("TMDB_API_KEY is not set in config.py")
        return []

    url = f"https://api.themoviedb.org/3/search/movie"
    params = {
        "api_key": TMDB_API_KEY,
        "query": query,
        "language": "en-US" # You can change this
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params) as response:
                response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
                data = await response.json()
                return data.get("results", [])
        except aiohttp.ClientError as e:
            logger.error(f"Error searching TMDB for '{query}': {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in TMDB search: {e}")
            return []

async def get_movie_details_tmdb(movie_id: int) -> dict | None:
    """Gets detailed information for a movie from TMDB."""
    if not TMDB_API_KEY:
        logger.error("TMDB_API_KEY is not set in config.py")
        return None

    url = f"https://api.themoviedb.org/3/movie/{movie_id}"
    params = {
        "api_key": TMDB_API_KEY,
        "language": "en-US"
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"Error fetching TMDB details for ID {movie_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in TMDB details fetch: {e}")
            return None

def get_tmdb_image_url(poster_path: str) -> str | None:
    """Constructs the full image URL from a TMDB poster path."""
    if poster_path:
        return f"{TMDB_IMAGE_BASE_URL}{poster_path}"
    return None
  
