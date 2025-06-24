%%writefile your_movie_bot/handlers/callbacks/user_requests.py
import logging
from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.enums import ParseMode

from utils.database import get_user_state, clear_user_state, add_movie_request, update_request_status
from config import ADMIN_CHAT_ID

logger = logging.getLogger(__name__)

async def handle_select_tmdb_callback(client: Client, callback_query: CallbackQuery):
    """
    Handles the user's selection of a movie from TMDB search results.
    Asks for confirmation and forwards to admin.
    """
    user_id = callback_query.from_user.id
    selected_tmdb_id = int(callback_query.data.split("_")[2]) # Extract TMDB ID from callback_data
    message = callback_query.message

    state, state_data = await get_user_state(user_id)

    if state != "awaiting_tmdb_selection" or not state_data or "results" not in state_data:
        await message.edit_text("Your previous search session has expired. Please use `/request <movie name>` again to start a new search.")
        await clear_user_state(user_id)
        return

    # Find the selected movie from the stored results
    selected_movie = next((m for m in state_data["results"] if m["id"] == selected_tmdb_id), None)

    if not selected_movie:
        await message.edit_text("Selected movie not found in results. Please try searching again.")
        await clear_user_state(user_id)
        return

    tmdb_title = selected_movie.get("title", "N/A")
    tmdb_year = selected_movie.get("release_date", "N/A").split("-")[0]
    tmdb_poster_path = selected_movie.get("poster_path")

    confirmation_text = (
        f"You selected: **{tmdb_title}** ({tmdb_year})\n\n"
        "Is this correct? Click 'Confirm Request' to proceed, or 'Cancel' to choose again."
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm Request", callback_data=f"confirm_request_{selected_tmdb_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="tmdb_none_correct")] # Re-use none correct to cancel/restart
    ])

    # Edit the original message to show confirmation
    try:
        await message.edit_text(
            confirmation_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        # Store the message_id of this confirmation message in user state
        await set_user_state(user_id, "awaiting_confirmation", {
            "tmdb_id": selected_tmdb_id,
            "tmdb_title": tmdb_title,
            "tmdb_poster_path": tmdb_poster_path,
            "message_id": message.id # The ID of the message being edited
        })
        logger.info(f"User {user_id} selected TMDB ID {selected_tmdb_id} for confirmation.")

    except Exception as e:
        logger.error(f"Error editing message for user {user_id} during TMDB selection: {e}")
        await message.reply_text("An error occurred. Please try `/request` again.")
        await clear_user_state(user_id)


async def handle_none_correct_callback(client: Client, callback_query: CallbackQuery):
    """Handles user indicating none of the TMDB results were correct or cancelling."""
    user_id = callback_query.from_user.id
    message = callback_query.message

    await message.edit_text(
        "Okay, please try a new `/request <movie name>` with a more precise title or different spelling."
    )
    await clear_user_state(user_id)
    logger.info(f"User {user_id} indicated none of the TMDB results were correct.")


async def handle_confirm_request_callback(client: Client, callback_query: CallbackQuery):
    """
    Handles the user's confirmation of a movie request.
    Adds to DB, notifies admin, and updates user message.
    """
    user_id = callback_query.from_user.id
    message = callback_query.message
    selected_tmdb_id = int(callback_query.data.split("_")[2])

    state, state_data = await get_user_state(user_id)

    if state != "awaiting_confirmation" or not state_data or state_data.get("tmdb_id") != selected_tmdb_id:
        await message.edit_text("This request session has expired or is invalid. Please use `/request <movie name>` to start a new one.")
        await clear_user_state(user_id)
        return

    tmdb_title = state_data.get("tmdb_title")
    tmdb_poster_path = state_data.get("tmdb_poster_path")
    user_name = callback_query.from_user.full_name or f"User_{user_id}"

    # First, update the user's original message
    await message.edit_text(
        f"✅ Request confirmed for **{tmdb_title}**. I've notified the administrator. "
        "You will be notified here when the movie is available! Thank you for your patience.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=None # Remove buttons
    )
    logger.info(f"User {user_id} confirmed request for TMDB ID {selected_tmdb_id}.")

    # Add request to database (initial 'pending' status)
    request_id = await add_movie_request(
        user_id=user_id,
        user_name=user_name,
        tmdb_id=selected_tmdb_id,
        tmdb_title=tmdb_title,
        tmdb_poster_path=tmdb_poster_path,
        admin_message_id=None # Will be updated after forwarding
    )
    logger.info(f"Movie request {request_id} added to DB for user {user_id}.")

    # Forward request to admin
    admin_message_text = (
        f"🎬 **New Movie Request!**\n\n"
        f"**User:** {user_name} (ID: `{user_id}`)\n"
        f"**Movie:** **{tmdb_title}** (TMDB ID: `{selected_tmdb_id}`)\n"
        f"**Status:** `Pending Approval`\n\n"
        "Please click 'Approve & Auto Index' if the movie is already uploaded to the channel with `#TMDB{ID}` in its caption."
    )

    admin_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Approve & Auto Index", callback_data=f"admin_approve_{request_id}")],
        [InlineKeyboardButton("❌ Reject Request", callback_data=f"admin_reject_{request_id}")]
    ])

    try:
        if tmdb_poster_path:
            poster_url = f"https://image.tmdb.org/t/p/w500{tmdb_poster_path}"
            admin_msg = await client.send_photo(
                chat_id=ADMIN_CHAT_ID,
                photo=poster_url,
                caption=admin_message_text,
                reply_markup=admin_keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            admin_msg = await client.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=admin_message_text,
                reply_markup=admin_keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
        # Update the admin_message_id in the database for this request
        await client.get_db_connection().execute("UPDATE movie_requests SET admin_message_id = ? WHERE id = ?", (admin_msg.id, request_id))
        await client.get_db_connection().commit()
        logger.info(f"Request {request_id} forwarded to admin chat {ADMIN_CHAT_ID} with message ID {admin_msg.id}.")

    except Exception as e:
        logger.error(f"Failed to forward request {request_id} to admin chat {ADMIN_CHAT_ID}: {e}", exc_info=True)
        # If forwarding fails, perhaps update user that admin couldn't be notified
        await message.reply_text("🚨 An error occurred while notifying the administrator. Please try again later.")

    await clear_user_state(user_id) # Clear user state after request is processed
    
