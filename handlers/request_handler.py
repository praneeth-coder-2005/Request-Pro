import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from utils.tmdb_api import search_movie_tmdb
from utils.database import set_user_state, clear_user_state, add_movie_request
from config import ADMIN_CHAT_ID, BOT_NAME # Import BOT_NAME for messages

logger = logging.getLogger(__name__)

@Client.on_message(filters.command("request") & filters.private)
async def request_command(client: Client, message: Message):
    """
    Handles the /request command, searches TMDB, and presents results to the user.
    """
    user_id = message.from_user.id
    movie_name = message.text.replace("/request", "").strip()

    if not movie_name:
        await message.reply_text("Please provide a movie name after the /request command. Example: `/request Inception`")
        await clear_user_state(user_id)
        return

    await message.reply_text(f"Searching for '{movie_name}' on TMDB... 🎬")
    logger.info(f"User {user_id} requested movie: {movie_name}")

    search_results = await search_movie_tmdb(movie_name)

    if not search_results:
        await message.reply_text(
            "Sorry, I couldn't find any movies matching that name on TMDB. "
            "Please try a different spelling or a more specific title."
        )
        await clear_user_state(user_id)
        logger.info(f"No TMDB results found for '{movie_name}' for user {user_id}.")
        return

    # Store search results temporarily in user's state
    # Only store necessary data to avoid large state objects
    user_search_data = {
        "query": movie_name,
        "results": [
            {"id": m["id"], "title": m["title"], "release_date": m["release_date"], "poster_path": m["poster_path"]}
            for m in search_results[:5] # Limit to top 5 results for brevity
        ]
    }
    await set_user_state(user_id, "awaiting_tmdb_selection", user_search_data)
    logger.debug(f"User {user_id} state set to 'awaiting_tmdb_selection'.")

    keyboard = []
    response_text = "I found these movies. Please select the correct one:\n\n"

    for i, movie in enumerate(search_results[:5]): # Show up to 5 results
        title = movie.get("title", "N/A")
        year = movie.get("release_date", "N/A").split("-")[0]
        movie_id = movie.get("id")

        response_text += f"**{i+1}. {title}** ({year})\n"
        keyboard.append([InlineKeyboardButton(f"{i+1}. {title} ({year})", callback_data=f"select_tmdb_{movie_id}")])

    keyboard.append([InlineKeyboardButton("None of these are correct", callback_data="tmdb_none_correct")])

    await message.reply_text(
        response_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    # Store the message ID so we can edit it later if user confirms
    await set_user_state(user_id, "awaiting_tmdb_selection", {**user_search_data, "message_id": message.id + 1}) # +1 because reply_text creates a new message

