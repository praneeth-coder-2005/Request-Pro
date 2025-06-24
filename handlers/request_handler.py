# handlers/request_handler.py
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.enums import ChatAction, ParseMode # ADDED ParseMode here
import logging

from utils.tmdb_api import search_movies_tmdb, get_tmdb_image_url # Changed search_tmdb_movies to search_movies_tmdb
from utils.database import set_user_state, clear_user_state, get_user_state
from utils.helpers import format_movie_info

logger = logging.getLogger(__name__)

@Client.on_message(filters.command("request") & filters.private)
async def handle_movie_request_command(client: Client, message: Message):
    user_id = message.from_user.id
    query = message.text.split(" ", 1)

    if len(query) < 2:
        await message.reply_text("Please provide a movie title to search for. Example: `/request The Matrix`")
        await clear_user_state(user_id)
        return

    movie_title = query[1].strip()
    logger.info(f"User {user_id} requested: '{movie_title}'")

    await client.send_chat_action(message.chat.id, ChatAction.TYPING)
    tmdb_results = await search_tmdb_movies(movie_title)

    if not tmdb_results:
        await message.reply_text("No results found. Please try a different query.", parse_mode=ParseMode.MARKDOWN) # FIXED
        await clear_user_state(user_id)
        return

    # Store TMDB results in user state for callback handling
    await set_user_state(user_id, "awaiting_tmdb_selection", {"tmdb_results": tmdb_results, "original_query": movie_title})
    logger.info(f"User {user_id} saved state 'awaiting_tmdb_selection'.")

    keyboard_buttons = []
    response_text = "Here are a few movies I found. Please select the correct one:\n\n"

    for i, movie in enumerate(tmdb_results[:5]): # Limit to top 5 results for brevity
        title = movie.get("title", "N/A")
        release_date = movie.get("release_date", "N/A")
        response_text += f"**{i+1}. {title}** ({release_date[:4] if release_date != 'N/A' else 'N/A'})\n"
        keyboard_buttons.append(
            [InlineKeyboardButton(f"{i+1}. {title} ({release_date[:4] if release_date != 'N/A' else 'N/A'})", callback_data=f"select_tmdb_{i}")]
        )

    keyboard_buttons.append([InlineKeyboardButton("None of these are correct", callback_data="tmdb_none_correct")])

    reply_markup = InlineKeyboardMarkup(keyboard_buttons)

    try:
        await message.reply_text(response_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN) # FIXED
        logger.info(f"User {user_id} searched for '{movie_title}', presented TMDB options.")
    except Exception as e:
        logger.error(f"Error sending TMDB search results to user {user_id}: {e}", exc_info=True)
        await message.reply_text("An error occurred while displaying search results. Please try again.")

