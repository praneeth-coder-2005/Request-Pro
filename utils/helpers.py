import logging
from pyrogram import Client
from utils.database import get_request_by_tmdb_id # Import the new DB function

logger = logging.getLogger(__name__)

async def search_channel_for_movie(client: Client, channel_id: str, tmdb_id: int):
    """
    Searches the bot's internal database for a movie that has already been fulfilled
    and has a channel_message_id. Returns the movie_request data if found, else None.
    Bots cannot directly search Telegram channel messages.
    """
    logger.info(f"Checking internal database for fulfilled movie with TMDB ID: {tmdb_id}")

    # Search the database for any request with this TMDB ID that has been fulfilled
    # and has a channel_message_id.
    movie_request_data = await get_request_by_tmdb_id(tmdb_id)

    if movie_request_data and movie_request_data.get("status") == "fulfilled" and movie_request_data.get("channel_message_id"):
        logger.info(f"Movie with TMDB ID {tmdb_id} found as fulfilled in DB, channel_message_id: {movie_request_data['channel_message_id']}")
        return movie_request_data # Return the full request data including channel_message_id
    else:
        logger.info(f"Movie with TMDB ID {tmdb_id} not found as fulfilled (or no channel_message_id) in DB.")
        return None # Movie not found in our index


def clean_movie_title(title: str) -> str:
    """Cleans a movie title for consistent searching."""
    # Example: remove common suffixes like (2023), (UHD), [1080p]
    # This is a very basic cleaning. More advanced cleaning might be needed.
    cleaned_title = title.split('(')[0].split('[')[0].strip()
    return cleaned_title

def format_movie_info(movie_data: dict) -> str:
    """Formats movie details for display."""
    title = movie_data.get('title', 'N/A')
    release_date = movie_data.get('release_date', 'N/A')
    overview = movie_data.get('overview', 'No overview available.')

    # Truncate long overviews
    if len(overview) > 500:
        overview = overview[:497] + "..."

    return (
        f"🎬 **Title:** {title}\n"
        f"🗓️ **Release Date:** {release_date}\n\n"
        f"📝 **Overview:** {overview}"
    )

def get_tmdb_image_url(poster_path: str, size: str = "w500") -> str:
    """Constructs a TMDB image URL."""
    if poster_path:
        return f"https://image.tmdb.org/t/p/{size}{poster_path}"
    return "https://via.placeholder.com/500x750?text=No+Poster" # Placeholder image
