# handlers/request_handler.py
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, ChatAction
import asyncio
import logging

from utils.tmdb_api import search_movie_tmdb, get_movie_details_tmdb, get_tmdb_image_url
from utils.database import set_user_state, clear_user_state, get_user_state, add_movie_request
from utils.helpers import search_channel_for_movie, clean_movie_title, format_movie_info
from config import MOVIE_CHANNEL_ID, ADMIN_CHAT_ID

logger = logging.getLogger(__name__)

@Client.on_message(filters.command("request") & filters.private)
async def handle_movie_request_command(client: Client, message: Message):
    """
    Handles user's movie requests, initiating TMDB search.
    """
    user_id = message.from_user.id
    search_query = " ".join(message.command[1:]).strip()

    if not search_query:
        await message.reply_text(
            "Please tell me the movie title you are looking for. "
            "Example: `/request Avengers Endgame`"
        )
        return

    await client.send_chat_action(message.chat.id, ChatAction.TYPING)

    movies = await search_movie_tmdb(search_query)

    if not movies:
        await message.reply_text(
            f"Sorry, I couldn't find any movies matching '{search_query}' on TMDB. "
            "Please double-check the spelling or try a different title."
        )
        await clear_user_state(user_id) # Clear any previous state
        return

    # Store TMDB results temporarily for user selection
    tmdb_results = []
    keyboard_buttons = []
    for i, movie in enumerate(movies[:5]): # Show top 5 results
        tmdb_results.append({
            "id": movie.get("id"),
            "title": movie.get("title"),
            "release_date": movie.get("release_date"),
            "overview": movie.get("overview"),
            "poster_path": movie.get("poster_path")
        })
        keyboard_buttons.append(
            [InlineKeyboardButton(
                f"{movie.get('title')} ({movie.get('release_date', 'N/A').split('-')[0]})",
                callback_data=f"select_tmdb_{i}"
            )]
        )

    # Add a "None of these" option
    keyboard_buttons.append(
        [InlineKeyboardButton("🚫 None of these are correct", callback_data="tmdb_none_correct")]
    )

    reply_markup = InlineKeyboardMarkup(keyboard_buttons)

    # Store results in user state for later callback handling
    await set_user_state(user_id, "awaiting_tmdb_selection", {"tmdb_results": tmdb_results, "original_query": search_query})

    await message.reply_text(
        "I found a few movies. Please select the correct one from the list below:",
        reply_markup=reply_markup
    )
    logger.info(f"User {user_id} searched for '{search_query}', presented TMDB options.")

