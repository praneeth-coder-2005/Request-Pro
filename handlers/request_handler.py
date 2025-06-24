# handlers/request_handler.py
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from pyrogram.enums import ChatAction # <-- This is the CORRECT way to import ChatAction in Pyrogram 2.x
import asyncio
import logging

# Import your own utility and config files
from utils.tmdb_api import search_movie_tmdb, get_movie_details_tmdb, get_tmdb_image_url
from utils.database import set_user_state, clear_user_state, get_user_state # Make sure these functions exist in your database.py
from utils.helpers import search_channel_for_movie, clean_movie_title, format_movie_info # Make sure these functions exist in your helpers.py
from config import MOVIE_CHANNEL_ID, ADMIN_CHAT_ID

logger = logging.getLogger(__name__)

# This tells Pyrogram to run this function when a user sends "/request" followed by text in a private chat
@Client.on_message(filters.command("request") & filters.private)
async def handle_movie_request_command(client: Client, message: Message):
    """
    Handles user's movie requests, initiating TMDB search and showing options.
    """
    user_id = message.from_user.id
    search_query = " ".join(message.command[1:]).strip() # Get the text after /request
    logger.info(f"User {user_id} requested: '{search_query}'")

    if not search_query:
        await message.reply_text(
            "Please tell me the movie title you are looking for. "
            "Example: `/request Avengers Endgame`"
        )
        return

    # Show "typing..." action in Telegram
    await client.send_chat_action(message.chat.id, ChatAction.TYPING)

    # Search for the movie on TMDB (The Movie Database)
    movies = await search_movie_tmdb(search_query)

    if not movies:
        await message.reply_text(
            f"Sorry, I couldn't find any movies matching '{search_query}' on TMDB. "
            "Please double-check the spelling or try a different title."
        )
        await clear_user_state(user_id) # Clear any previous user state
        return

    # Prepare results to show to the user as buttons
    tmdb_results = []
    keyboard_buttons = []
    for i, movie in enumerate(movies[:5]): # Show up to the top 5 results
        tmdb_results.append({
            "id": movie.get("id"),
            "title": movie.get("title"),
            "release_date": movie.get("release_date"),
            "overview": movie.get("overview"),
            "poster_path": movie.get("poster_path")
        })
        keyboard_buttons.append(
            [InlineKeyboardButton( # Create a button for each movie
                f"{movie.get('title')} ({movie.get('release_date', 'N/A').split('-')[0] if movie.get('release_date') else 'N/A'})",
                callback_data=f"select_tmdb_{i}" # This data will be sent back when button is clicked
            )]
        )

    # Add a "None of these" button
    keyboard_buttons.append(
        [InlineKeyboardButton("🚫 None of these are correct", callback_data="tmdb_none_correct")]
    )

    reply_markup = InlineKeyboardMarkup(keyboard_buttons)

    # Save these results temporarily in the user's state in the database
    await set_user_state(user_id, "awaiting_tmdb_selection", {"tmdb_results": tmdb_results, "original_query": search_query})
    logger.info(f"User {user_id} saved state 'awaiting_tmdb_selection'.")

    await message.reply_text(
        "I found a few movies. Please select the correct one from the list below:",
        reply_markup=reply_markup # Attach the buttons to the message
    )
    logger.info(f"User {user_id} searched for '{search_query}', presented TMDB options.")

