%%writefile your_movie_bot/utils/tmdb_api.py
import logging
import asyncio # New import for running synchronous code asynchronously
from tmdbv3api import TMDb, Movie # New imports for the tmdbv3api library
from config import TMDB_API_KEY

logger = logging.getLogger(__name__)

# Initialize TMDb API client once globally
tmdb = TMDb()
movie_api = Movie() # Create an instance of Movie API as it's reusable

async def search_movie_tmdb(query: str):
    """Searches for movies on TMDB using tmdbv3api."""
    if not TMDB_API_KEY:
        logger.error("TMDB_API_KEY is not set in config.py")
        return []

    # Set API key for the current instance.
    # This is important if `tmdb` object is reused across async tasks.
    tmdb.api_key = TMDB_API_KEY

    try:
        # Run the synchronous API call in a separate thread to avoid blocking the event loop
        search_results = await asyncio.to_thread(movie_api.search, query)

        movies = []
        for movie in search_results:
            # tmdbv3api objects directly have attributes for movie data
            if not movie.adult: # Filter out adult content
                movies.append({
                    "id": movie.id,
                    "title": movie.title,
                    "release_date": movie.release_date if hasattr(movie, 'release_date') else "N/A",
                    "poster_path": movie.poster_path
                })
        return movies
    except Exception as e:
        logger.error(f"An error occurred during TMDB search with tmdbv3api: {e}", exc_info=True)
        return []
        
