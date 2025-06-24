# handlers/callbacks/user_requests.py
import logging
from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from pyrogram.enums import ChatAction, ParseMode # ADDED ParseMode here

from utils.tmdb_api import get_movie_details_tmdb, get_tmdb_image_url
from utils.database import get_user_state, clear_user_state, set_user_state, add_movie_request, update_request_status, get_request_by_tmdb_id, update_request_admin_message_id
from utils.helpers import search_channel_for_movie, format_movie_info
from config import ADMIN_CHAT_ID, MOVIE_CHANNEL_ID # Include ADMIN_CHAT_ID here

logger = logging.getLogger(__name__)

async def handle_select_tmdb_callback(client: Client, callback_query: CallbackQuery):
    """Handles user selecting a movie from TMDB search results."""
    data = callback_query.data
    user_id = callback_query.from_user.id
    message = callback_query.message
    chat_id = message.chat.id

    logger.info(f"User {user_id} selected a TMDB movie option: {data}")
    state, state_data = await get_user_state(user_id)
    logger.info(f"User {user_id} current state: {state}, data: {state_data}")

    if state != "awaiting_tmdb_selection" or not state_data or "tmdb_results" not in state_data:
        logger.warning(f"User {user_id} clicked an old or invalid 'select_tmdb' button. State: {state}")
        await message.edit_text("This selection is no longer valid. Please start a new `/request`.")
        await clear_user_state(user_id)
        return

    selected_index = int(data.split("_")[2])
    tmdb_results = state_data["tmdb_results"]

    if selected_index >= len(tmdb_results) or selected_index < 0:
        logger.error(f"User {user_id} selected invalid index {selected_index} for TMDB results (length {len(tmdb_results)}).")
        await message.edit_text("Invalid selection. Please try again or start a new `/request`.")
        return

    selected_movie_preview = tmdb_results[selected_index]
    tmdb_id = selected_movie_preview["id"]

    await client.send_chat_action(chat_id, ChatAction.TYPING)

    full_movie_details = await get_movie_details_tmdb(tmdb_id)
    if not full_movie_details:
        logger.error(f"Failed to retrieve full TMDB details for ID {tmdb_id} for user {user_id}.")
        await message.edit_text("Could not retrieve full movie details. Please try again or search for a different movie.")
        await clear_user_state(user_id)
        return

    formatted_info = format_movie_info(full_movie_details)
    poster_url = get_tmdb_image_url(full_movie_details.get("poster_path"))

    await set_user_state(user_id, "awaiting_confirmation", {"movie_data": full_movie_details})
    logger.info(f"User {user_id} entered 'awaiting_confirmation' state with movie: {full_movie_details.get('title')}")

    confirmation_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, this is correct!", callback_data=f"confirm_request_true")],
        [InlineKeyboardButton("❌ No, go back to search results", callback_data=f"confirm_request_false")]
    ])

    try:
        if poster_url:
            await message.edit_media(
                media=InputMediaPhoto(poster_url, caption=f"Is this the movie you are looking for?\n\n{formatted_info}"),
                reply_markup=confirmation_keyboard
            )
        else:
            await message.edit_text(
                f"Is this the movie you are looking for?\n\n{formatted_info}",
                reply_markup=confirmation_keyboard,
                parse_mode=ParseMode.MARKDOWN, # FIXED
                disable_web_page_preview=True
            )
        logger.info(f"User {user_id} selected TMDB ID {tmdb_id}, presented for confirmation with media/text.")
    except Exception as e:
        logger.error(f"Error editing message with TMDB info for user {user_id}: {e}")
        await message.edit_text(
            f"Is this the movie you are looking for?\n\n{formatted_info}\n\n"
            "I couldn't display the poster. Please confirm manually.",
            reply_markup=confirmation_keyboard,
            parse_mode=ParseMode.MARKDOWN, # FIXED
            disable_web_page_preview=True
        )

async def handle_none_correct_callback(client: Client, callback_query: CallbackQuery):
    """Handles user indicating none of the TMDB results were correct."""
    user_id = callback_query.from_user.id
    message = callback_query.message
    logger.info(f"User {user_id} chose 'None of these are correct'.")
    await message.edit_text(
        "Okay, if none of those were correct, please try a different /request with a more specific title."
    )
    await clear_user_state(user_id)

async def handle_confirm_request_callback(client: Client, callback_query: CallbackQuery):
    """Handles user confirming or rejecting their movie request."""
    data = callback_query.data
    user_id = callback_query.from_user.id
    message = callback_query.message
    chat_id = message.chat.id

    logger.info(f"User {user_id} is confirming request: {data}")
    state, state_data = await get_user_state(user_id)
    if state != "awaiting_confirmation" or not state_data or "movie_data" not in state_data:
        logger.warning(f"User {user_id} clicked old or invalid 'confirm_request' button. State: {state}")
        await message.edit_text("This confirmation is no longer valid. Please start a new `/request`.")
        await clear_user_state(user_id)
        return

    confirmed = data.split("_")[2] == "true"
    movie_data = state_data["movie_data"]

    await clear_user_state(user_id)
    logger.info(f"User {user_id} cleared state after confirmation decision.")

    if not confirmed:
        logger.info(f"User {user_id} cancelled confirmation for {movie_data.get('title')}.")
        await message.edit_text("Okay, let's try again. Please use `/request` with a different title.")
        return

    await message.edit_text("Thanks for confirming! Checking if already available...")
    await client.send_chat_action(chat_id, ChatAction.TYPING)
    logger.info(f"User {user_id} confirmed '{movie_data.get('title')}', checking internal index.")

    # 1. Check if movie is already in the channel (via our database index)
    found_movie_request = await search_channel_for_movie(
        client, MOVIE_CHANNEL_ID, movie_data.get("id") # Pass TMDB ID
    )

    if found_movie_request:
        # Movie found in our database index
        channel_msg_id = found_movie_request["channel_message_id"]
        movie_title = found_movie_request["tmdb_title"]
        # Use the fulfilled_link if available from the DB for the Go To Movie button,
        # otherwise generate a direct permalink if only channel_msg_id is present.
        go_to_movie_url = found_movie_request.get("fulfilled_link") or f"https://t.me/{MOVIE_CHANNEL_ID.lstrip('@')}/{channel_msg_id}"


        try:
            # Copy the message from the channel to the user
            await client.copy_message(
                chat_id=user_id,
                from_chat_id=MOVIE_CHANNEL_ID,
                message_id=channel_msg_id
            )
            # Offer a button to go to the original message in the channel too
            reply_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Go to Movie in Channel 🎬", url=go_to_movie_url)]
            ])
            await message.edit_text(
                f"🎉 Great news! **{movie_title}** is already available. Here it is! Enjoy your movie. 🎬",
                parse_mode=ParseMode.MARKDOWN, # FIXED
                reply_markup=reply_keyboard
            )
            logger.info(f"User {user_id} requested '{movie_title}', found in DB index and sent from channel (Message ID: {channel_msg_id}).")
        except Exception as e:
            logger.error(f"Error copying found movie (ID {channel_msg_id}) to {user_id}: {e}", exc_info=True)
            await message.edit_text(
                "I found the movie in my index, but encountered an error sending it. "
                "It might have been deleted from the channel, or an issue occurred. "
                "Please try again later or contact support."
            )
        return # IMPORTANT: Add return here to stop further execution if movie is found
    else:
        # Movie not found in internal index, proceed to request admin
        request_data = {
            "user_id": user_id,
            "user_name": callback_query.from_user.first_name,
            "tmdb_id": movie_data.get("id"),
            "tmdb_title": movie_data.get("title"),
            "tmdb_overview": movie_data.get("overview"),
            "tmdb_poster_path": movie_data.get("poster_path"),
            "original_user_request_msg_id": message.id # Store message ID for later editing
        }
        request_id = await add_movie_request(request_data)

        if not request_id:
            logger.error(f"Failed to add movie request for user {user_id} and movie {movie_data.get('title')}.")
            await message.edit_text("An error occurred while processing your request. Please try again.")
            return

        admin_message_caption = (
            f"🎬 **New Movie Request** (ID: `{request_id}`)\n\n"
            f"**From User:** [{callback_query.from_user.first_name}](tg://user?id={user_id})\n"
            f"**Requested Movie:** `{movie_data.get('title')}`\n"
            f"**Release Date:** `{movie_data.get('release_date', 'N/A')}`\n"
            f"**Overview:** {movie_data.get('overview', 'No overview available.')}\n\n"
            f"Please upload this movie to the channel."
        )
        admin_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Approve & Fulfill", callback_data=f"admin_approve_{request_id}")],
            [InlineKeyboardButton("❌ Reject Request", callback_data=f"admin_reject_{request_id}")]
        ])

        poster_url = get_tmdb_image_url(movie_data.get("poster_path"))
        try:
            admin_msg = await client.send_photo(
                chat_id=ADMIN_CHAT_ID,
                photo=poster_url if poster_url else "https://via.placeholder.com/500x750?text=No+Poster",
                caption=admin_message_caption,
                parse_mode=ParseMode.MARKDOWN, # FIXED
                reply_markup=admin_keyboard
            )
        except Exception as e:
            logger.error(f"Error sending TMDB photo to admin {ADMIN_CHAT_ID}: {e}. Sending text message instead.")
            admin_msg = await client.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=admin_message_caption + "\n(Poster failed to load)",
                parse_mode=ParseMode.MARKDOWN, # FIXED
                reply_markup=admin_keyboard,
                disable_web_page_preview=True
            )

        await update_request_admin_message_id(request_id, admin_msg.id)

        await message.edit_text(
            f"⏳ Your request for **{movie_data.get('title')}** has been submitted! "
            "It's not yet available in our channel. We've forwarded it to the admin "
            "and will notify you once it's uploaded. Thank you for your patience! 🙏",
            parse_mode=ParseMode.MARKDOWN # FIXED
        )
        logger.info(f"User {user_id} requested '{movie_data.get('title')}' (TMDB ID {movie_data.get('id')}), forwarded to admin (Request ID: {request_id}).")
    
