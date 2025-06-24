# utils/helpers.py
from pyrogram import Client
from pyrogram.types import Message
import re
from rapidfuzz import fuzz
from config import TMDB_IMAGE_BASE_URL
from utils.tmdb_api import get_tmdb_image_url

async def search_channel_for_movie(
    client: Client, channel_id: int, movie_title_fuzzy_match: str, limit: int = 100
) -> Message | None:
    """
    Searches a channel's history for a movie title using fuzzy matching.
    `movie_title_fuzzy_match` should be the cleaned, official title for better matching.
    """
    # Start with a direct query (cleaned title)
    async for message in client.search_messages(
        chat_id=channel_id, query=movie_title_fuzzy_match, limit=limit
    ):
        content = message.text or message.caption
        if content:
            cleaned_content = clean_movie_title(content)
            # Higher threshold for direct search
            if fuzz.ratio(cleaned_content, movie_title_fuzzy_match) > 85:
                return message

    # If not found directly, try broader search (original query or parts of it if needed)
    # This might require more advanced text analysis if you have complex channel naming
    # For now, we'll rely heavily on the initial direct search with the TMDB title.
    return None

def clean_movie_title(title: str) -> str:
    """
    Cleans a movie title for better comparison (e.g., removes special characters, common year patterns).
    """
    title = title.lower()
    title = re.sub(r"\[.*?\]|\(.*?\)", "", title) # Remove text in brackets/parentheses
    title = re.sub(r"\d{4}", "", title) # Remove 4-digit years
    title = re.sub(r"[^a-z0-9\s]", "", title) # Remove non-alphanumeric characters
    title = re.sub(r"\s+", " ", title).strip() # Replace multiple spaces with single space
    return title

def format_movie_info(movie_data: dict) -> str:
    """Formats TMDB movie details into a readable string."""
    title = movie_data.get("title", "N/A")
    release_date = movie_data.get("release_date", "N/A")
    overview = movie_data.get("overview", "No overview available.")
    poster_path = movie_data.get("poster_path")
    poster_url = get_tmdb_image_url(poster_path) if poster_path else "No Poster"

    info = (
        f"🎬 **Title:** `{title}`\n"
        f"📅 **Release Date:** `{release_date}`\n\n"
        f"📖 **Overview:**\n{overview}\n\n"
        f"[Poster]({poster_url})" if poster_url else "No poster available."
    )
    return info
  
