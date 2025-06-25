import httpx
import logging
import os

logger = logging.getLogger(__name__)

# Load TMDB API Key from environment variables
TMDB_API_KEY = os.environ.get("TMDB_API_KEY")
TMDB_BASE_URL = "https://api.themoviedb.org/3"

async def search_movies_tmdb(query: str) -> list:
    """
    Searches for movies on TMDB using the provided query.
    Returns a list of dictionaries, each containing relevant movie details.
    """
    if not TMDB_API_KEY:
        logger.error("TMDB_API_KEY is not set in environment variables.")
        return []

    url = f"{TMDB_BASE_URL}/search/movie"
    params = {
        "api_key": TMDB_API_KEY,
        "query": query,
        "include_adult": False # Exclude adult content
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
            data = response.json()
            movies = data.get("results", [])

            # Extract relevant fields for each movie
            extracted_movies = []
            for movie in movies:
                extracted_movies.append({
                    "id": movie.get("id"),
                    "title": movie.get("title"),
                    "release_date": movie.get("release_date"),
                    "overview": movie.get("overview"),
                    "poster_path": movie.get("poster_path")
                })
            return extracted_movies
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error searching TMDB for '{query}': {e.response.status_code} - {e.response.text}")
    except httpx.RequestError as e:
        logger.error(f"Network error searching TMDB for '{query}': {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while searching TMDB for '{query}': {e}", exc_info=True)
    return []

async def get_movie_details_tmdb(movie_id: int) -> dict:
    """
    Fetches detailed information for a specific movie from TMDB.
    """
    if not TMDB_API_KEY:
        logger.error("TMDB_API_KEY is not set in environment variables.")
        return {}

    url = f"{TMDB_BASE_URL}/movie/{movie_id}"
    params = {
        "api_key": TMDB_API_KEY
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching TMDB details for movie ID {movie_id}: {e.response.status_code} - {e.response.text}")
    except httpx.RequestError as e:
        logger.error(f"Network error fetching TMDB details for movie ID {movie_id}: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching TMDB details for movie ID {movie_id}: {e}", exc_info=True)
    return {}

def get_tmdb_image_url(poster_path: str, size: str = "w500") -> str:
    """
    Constructs a TMDB image URL.
    """
    if poster_path:
        return f"https://image.tmdb.org/t/p/{size}{poster_path}"
    return "https://via.placeholder.com/500x750?text=No+Poster" # Placeholder image

