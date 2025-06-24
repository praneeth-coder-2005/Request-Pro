%%writefile your_movie_bot/utils/tmdb_api.py
import aiohttp
import logging
from config import TMDB_API_KEY, TMDB_BASE_URL

logger = logging.getLogger(__name__)

async def search_movie_tmdb(query: str):
    """Searches for movies on TMDB."""
    if not TMDB_API_KEY:
        logger.error("TMDB_API_KEY is not set in config.py")
        return []

    url = f"{TMDB_BASE_URL}/search/movie"
    params = {
        "api_key": TMDB_API_KEY,
        "query": query
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                response.raise_for_status() # Raise an exception for HTTP errors
                data = await response.json()
                # Filter out adult content and return relevant fields
                movies = []
                for movie in data.get("results", []):
                    if not movie.get("adult", False):
                        movies.append({
                            "id": movie.get("id"),
                            "title": movie.get("title"),
                            "release_date": movie.get("release_date", "N/A"),
                            "poster_path": movie.get("poster_path")
                        })
                return movies
    except aiohttp.ClientError as e:
        logger.error(f"TMDB API request failed: {e}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"An unexpected error occurred during TMDB search: {e}", exc_info=True)
        return []

