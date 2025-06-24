# handlers/callback_handler.py
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Message
from pyrogram.enums import ChatAction # <-- Correct import for ChatAction
import asyncio
import logging

# Import your own utility and config files
from utils.tmdb_api import get_movie_details_tmdb, get_tmdb_image_url
from utils.database import get_user_state, clear_user_state, add_movie_request, update_request_status, get_request_by_id, update_request_admin_message_id
from utils.helpers import search_channel_for_movie, clean_movie_title, format_movie_info
from config import MOVIE_CHANNEL_ID, ADMIN_CHAT_ID

logger = logging.getLogger(__name__)

# This tells Pyrogram to run this function whenever an inline button is clicked
@Client.on_callback_query()
async def handle_callback_query(client: Client, callback_query: CallbackQuery):
    """
    Handles all inline keyboard callback queries (button clicks).
    """
    data = callback_query.data # This is the 'callback_data' from the button
    user_id = callback_query.from_user.id
    message = callback_query.message # The message where the button was clicked
    chat_id = message.chat.id # The chat where the message is

    logger.info(f"CallbackQuery received: {data} from user {user_id}")

    # Acknowledge the callback immediately. This makes the button stop "loading"
    # and prevents the "This query is too old" popup for the user.
    await callback_query.answer()

    # --- Handle User TMDB Movie Selection (after /request) ---
    if data.startswith("select_tmdb_"):
        logger.info(f"User {user_id} selected a TMDB movie option: {data}")
        state, state_data = await get_user_state(user_id) # Get the user's current state from the database
        logger.info(f"User {user_id} current state: {state}, data: {state_data}")

        # Check if the user is in the correct state to make this selection
        if state != "awaiting_tmdb_selection" or not state_data or "tmdb_results" not in state_data:
            logger.warning(f"User {user_id} clicked an old or invalid 'select_tmdb' button. State: {state}")
            await message.edit_text("This selection is no longer valid. Please start a new `/request`.")
            await clear_user_state(user_id)
            return

        selected_index = int(data.split("_")[2]) # Extract the index from the callback data (e.g., "select_tmdb_0" -> 0)
        tmdb_results = state_data["tmdb_results"] # Get the stored TMDB results for this user

        # Check if the selected index is valid
        if selected_index >= len(tmdb_results) or selected_index < 0:
            logger.error(f"User {user_id} selected invalid index {selected_index} for TMDB results (length {len(tmdb_results)}).")
            await message.edit_text("Invalid selection. Please try again or start a new `/request`.")
            return

        selected_movie_preview = tmdb_results[selected_index]
        tmdb_id = selected_movie_preview["id"] # Get the TMDB ID of the selected movie

        await client.send_chat_action(chat_id, ChatAction.TYPING) # Show typing action

        # Get full movie details from TMDB using the ID
        full_movie_details = await get_movie_details_tmdb(tmdb_id)
        if not full_movie_details:
            logger.error(f"Failed to retrieve full TMDB details for ID {tmdb_id} for user {user_id}.")
            await message.edit_text("Could not retrieve full movie details. Please try again or search for a different movie.")
            await clear_user_state(user_id)
            return

        formatted_info = format_movie_info(full_movie_details) # Format the movie info nicely
        poster_url = get_tmdb_image_url(full_movie_details.get("poster_path")) # Get the poster image URL

        # Save the selected movie details in the user's state for the next step (confirmation)
        await set_user_state(user_id, "awaiting_confirmation", {"movie_data": full_movie_details})
        logger.info(f"User {user_id} entered 'awaiting_confirmation' state with movie: {full_movie_details.get('title')}")

        # Create confirmation buttons
        confirmation_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes, this is correct!", callback_data=f"confirm_request_true")],
            [InlineKeyboardButton("❌ No, go back to search results", callback_data=f"confirm_request_false")]
        ])

        # Try to edit the message with the poster and movie info
        try:
            if poster_url:
                await message.edit_media(
                    media=InputMediaPhoto(poster_url, caption=f"Is this the movie you are looking for?\n\n{formatted_info}"),
                    reply_markup=confirmation_keyboard
                )
            else: # If no poster, just send text
                await message.edit_text(
                    f"Is this the movie you are looking for?\n\n{formatted_info}",
                    reply_markup=confirmation_keyboard,
                    parse_mode="markdown",
                    disable_web_page_preview=True # Prevent Telegram from making its own link preview
                )
            logger.info(f"User {user_id} selected TMDB ID {tmdb_id}, presented for confirmation with media/text.")
        except Exception as e: # Catch errors if editing message fails (e.g., bad poster URL)
            logger.error(f"Error editing message with TMDB info for user {user_id}: {e}")
            # Fallback to sending text if photo fails
            await message.edit_text(
                f"Is this the movie you are looking for?\n\n{formatted_info}\n\n"
                "I couldn't display the poster. Please confirm manually.",
                reply_markup=confirmation_keyboard,
                parse_mode="markdown",
                disable_web_page_preview=True
            )

    # --- Handle "None of these are correct" button ---
    elif data == "tmdb_none_correct":
        logger.info(f"User {user_id} chose 'None of these are correct'.")
        await message.edit_text(
            "Okay, if none of those were correct, please try a different /request with a more specific title."
        )
        await clear_user_state(user_id) # Clear user's state

    # --- Handle User Request Confirmation (Yes/No buttons) ---
    elif data.startswith("confirm_request_"):
        logger.info(f"User {user_id} is confirming request: {data}")
        state, state_data = await get_user_state(user_id)
        if state != "awaiting_confirmation" or not state_data or "movie_data" not in state_data:
            logger.warning(f"User {user_id} clicked old or invalid 'confirm_request' button. State: {state}")
            await message.edit_text("This confirmation is no longer valid. Please start a new `/request`.")
            await clear_user_state(user_id)
            return

        confirmed = data.split("_")[2] == "true" # Check if user clicked 'true' or 'false'
        movie_data = state_data["movie_data"] # Get the selected movie details

        await clear_user_state(user_id) # Clear state after user's decision
        logger.info(f"User {user_id} cleared state after confirmation decision.")

        if not confirmed: # If user clicked 'No'
            logger.info(f"User {user_id} cancelled confirmation for {movie_data.get('title')}.")
            await message.edit_text("Okay, let's try again. Please use `/request` with a different title.")
            return

        # If user confirmed the movie:
        await message.edit_text("Thanks for confirming! Checking our channel now...")
        await client.send_chat_action(chat_id, ChatAction.TYPING)
        logger.info(f"User {user_id} confirmed '{movie_data.get('title')}', checking channel.")

        # 1. Check if movie is already in the channel
        cleaned_tmdb_title = clean_movie_title(movie_data.get("title"))
        found_movie_message = await search_channel_for_movie(
            client, MOVIE_CHANNEL_ID, cleaned_tmdb_title
        )

        if found_movie_message:
            # Movie found in channel, send it to the user
            try:
                await client.copy_message( # Pyrogram's way to forward a message without showing "Forwarded from"
                    chat_id=user_id,
                    from_chat_id=MOVIE_CHANNEL_ID,
                    message_id=found_movie_message.id
                )
                await message.edit_text(
                    f"🎉 Great news! **{movie_data.get('title')}** is already available. Here it is! Enjoy your movie. 🎬",
                    parse_mode="markdown"
                )
                logger.info(f"User {user_id} requested '{movie_data.get('title')}', found and sent from channel.")
            except Exception as e:
                logger.error(f"Error sending found movie to {user_id}: {e}")
                await message.edit_text(
                    "I found the movie, but encountered an error sending it. "
                    "Please try again later or contact support."
                )
            return # IMPORTANT: Add return here to stop further execution if movie is found
        else:
            # Movie not found in channel, send request to admin
            # Add request to database
            request_data = {
                "user_id": user_id,
                "user_name": callback_query.from_user.first_name,
                "tmdb_id": movie_data.get("id"),
                "tmdb_title": movie_data.get("title"),
                "tmdb_overview": movie_data.get("overview"),
                "tmdb_poster_path": movie_data.get("poster_path"),
                "original_user_request_msg_id": message.id # Store user's message ID for later editing
            }
            request_id = await add_movie_request(request_data) # This adds it to your database

            if not request_id:
                logger.error(f"Failed to add movie request for user {user_id} and movie {movie_data.get('title')}.")
                await message.edit_text(
                    "An error occurred while processing your request. Please try again."
                )
                return

            # Prepare message and buttons for the admin
            admin_message_caption = (
                f"🎬 **New Movie Request** (ID: `{request_id}`)\n\n"
                f"**From User:** [{callback_query.from_user.first_name}](tg://user?id={user_id})\n"
                f"**Requested Movie:** `{movie_data.get('title')}`\n"
                f"**Release Date:** `{movie_data.get('release_date', 'N/A')}`\n"
                f"**Overview:** {movie_data.get('overview', 'No overview available.')}\n\n"
                f"Please upload this movie to the channel.\n"
            )
            admin_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Approve & Fulfill", callback_data=f"admin_approve_{request_id}")],
                [InlineKeyboardButton("❌ Reject Request", callback_data=f"admin_reject_{request_id}")]
            ])

            poster_url = get_tmdb_image_url(movie_data.get("poster_path"))
            try:
                # Send photo with details to the admin
                admin_msg = await client.send_photo(
                    chat_id=ADMIN_CHAT_ID,
                    photo=poster_url if poster_url else "https://via.placeholder.com/500x750?text=No+Poster", # Fallback if no poster
                    caption=admin_message_caption,
                    parse_mode="markdown",
                    reply_markup=admin_keyboard
                )
            except Exception as e:
                logger.error(f"Error sending TMDB photo to admin {ADMIN_CHAT_ID}: {e}. Sending text message instead.")
                # If sending photo fails, send a text message instead
                admin_msg = await client.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=admin_message_caption + "\n(Poster failed to load)",
                    parse_mode="markdown",
                    reply_markup=admin_keyboard,
                    disable_web_page_preview=True
                )

            await update_request_admin_message_id(request_id, admin_msg.id) # Save the admin message ID

            # Notify the user that their request has been forwarded
            await message.edit_text(
                f"⏳ Your request for **{movie_data.get('title')}** has been submitted! "
                "It's not yet available in our channel. We've forwarded it to the admin "
                "and will notify you within 12 hours once it's uploaded. Thank you for your patience! 🙏",
                parse_mode="markdown"
            )
            logger.info(f"User {user_id} requested '{movie_data.get('title')}' (TMDB ID {movie_data.get('id')}), forwarded to admin (Request ID: {request_id}).")

    # --- Admin Action Callbacks (Approve, Reject, Fulfill) ---
    # These are the buttons the ADMIN clicks to manage requests
    elif data.startswith("admin_approve_"):
        request_id = int(data.split("_")[2])
        request_data = await get_request_by_id(request_id)

        if not request_data or request_data["status"] != "pending":
            await message.edit_text(f"Request ID `{request_id}` is not pending or does not exist.")
            logger.warning(f"Admin tried to approve non-pending request {request_id}. Status: {request_data['status'] if request_data else 'None'}")
            return

        await update_request_status(request_id, "approved_by_admin") # Update status in DB

        # Change admin message buttons
        await message.edit_reply_markup(reply_markup=None) # Remove old buttons
        await message.edit_caption(
            caption=message.caption + "\n\n✅ **Approved by Admin.**\n\n"
                    "Now, please use the buttons below to upload the movie files/links. "
                    "You can send multiple files/links if needed.",
            parse_mode="markdown",
            reply_markup=InlineKeyboardMarkup([ # New buttons for admin to upload/complete
                [InlineKeyboardButton("⬆️ Upload Files (Reply to this)", callback_data=f"admin_upload_files_{request_id}")],
                [InlineKeyboardButton("🔗 Upload URL (Reply to this)", callback_data=f"admin_upload_url_{request_id}")],
                [InlineKeyboardButton("✅ Fulfill (Done Uploading)", callback_data=f"admin_complete_fulfillment_{request_id}")]
            ])
        )
        logger.info(f"Admin approved request {request_id}. Awaiting file/URL upload.")

    elif data.startswith("admin_reject_"):
        request_id = int(data.split("_")[2])
        request_data = await get_request_by_id(request_id)

        if not request_data or request_data["status"] != "pending":
            await message.edit_text(f"Request ID `{request_id}` is not pending or does not exist.")
            logger.warning(f"Admin tried to reject non-pending request {request_id}. Status: {request_data['status'] if request_data else 'None'}")
            return

        await update_request_status(request_id, "rejected") # Update status in DB
        await message.edit_reply_markup(reply_markup=None) # Remove buttons
        await message.edit_caption(
            caption=message.caption + "\n\n❌ **Request Rejected by Admin.**",
            parse_mode="markdown"
        )
        try:
            # Notify the user that their request was rejected
            await client.send_message(
                chat_id=request_data["user_id"],
                text=f"🙁 We're sorry, your request for **{request_data['tmdb_title']}** could not be fulfilled at this time. "
                     "Please try again later or request a different movie.",
                parse_mode="markdown"
            )
        except Exception as e:
            logger.warning(f"Failed to notify user {request_data['user_id']} about rejected request {request_id}: {e}")
        logger.info(f"Admin rejected request {request_id}.")

    elif data.startswith("admin_upload_files_") or data.startswith("admin_upload_url_"):
        request_id = int(data.split("_")[2])
        # Just answer the callback, the actual upload is handled by admin_handler.py's reply filter
        await callback_query.answer("Please reply to THIS message with the files or URL(s).")
        logger.info(f"Admin clicked upload button for request {request_id}. Prompted for reply.")

    elif data.startswith("admin_complete_fulfillment_"):
        request_id = int(data.split("_")[3])
        request_data = await get_request_by_id(request_id)

        if not request_data or request_data["status"] not in ("approved_by_admin", "fulfilled"): # 'fulfilled' here means if they click it again
            await message.edit_text(f"Request ID `{request_id}` is not in a fulfillable state.")
            logger.warning(f"Admin tried to complete fulfillment for request {request_id} in invalid state: {request_data['status'] if request_data else 'None'}")
            return

        fulfilled_link = request_data.get("fulfilled_link", "Uploaded to channel.") # Get the link if any

        await update_request_status(request_id, "fulfilled", fulfilled_link) # Mark as fulfilled in DB

        user_id_to_notify = request_data["user_id"]
        tmdb_title = request_data["tmdb_title"]
        user_msg_id = request_data.get("original_user_request_msg_id")

        try:
            final_user_message_text = (
                f"🎉 Great news! Your requested movie, **{tmdb_title}**, is now available!\n\n"
            )
            # IMPORTANT: REPLACE "yourchannelusername" with your actual Telegram channel's username (e.g., @MyAwesomeMovies)
            go_to_movie_url = f"https://t.me/yourchannelusername"
            if fulfilled_link and fulfilled_link != "Uploaded to channel.":
                # If specific link was provided by admin, use that
                final_user_message_text += f"Click here to watch: {fulfilled_link}\n\n"
                go_to_movie_url = fulfilled_link # Use specific link for the button
            else:
                # If admin just uploaded to channel directly, guide user to channel
                final_user_message_text += f"It has been uploaded to our main channel.\n\n"
                f"You can search for it in your channel or click the button below.\n\n"

            final_user_message_text += "Enjoy your movie! 🍿"

            reply_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Go to Movie 🎬", url=go_to_movie_url)]
            ])

            # Try to edit the user's original request message to notify them
            if user_msg_id:
                try:
                    await client.edit_message_text(
                        chat_id=user_id_to_notify,
                        message_id=user_msg_id,
                        text=final_user_message_text,
                        parse_mode="markdown",
                        reply_markup=reply_keyboard
                    )
                except Exception as e:
                    logger.warning(f"Could not edit original user message {user_msg_id} for user {user_id_to_notify}: {e}. Sending new message instead.")
                    # If editing fails (e.g., message too old), send a new message
                    await client.send_message(
                        chat_id=user_id_to_notify,
                        text=final_user_message_text,
                        parse_mode="markdown",
                        reply_markup=reply_keyboard
                    )
            else: # If original message ID wasn't stored or is null
                await client.send_message(
                    chat_id=user_id_to_notify,
                    text=final_user_message_text,
                    parse_mode="markdown",
                    reply_markup=reply_keyboard
                )

            # Update the admin's message to show fulfillment is complete
            await message.edit_caption(
                caption=message.caption + f"\n\n✅ **Fulfillment Complete!** Notified user. Link: {fulfilled_link}",
                parse_mode="markdown",
                reply_markup=None # Remove all buttons from admin message
            )
            logger.info(f"Request {request_id} for '{tmdb_title}' fully fulfilled and user notified.")

        except Exception as e:
            logger.error(f"Error during final user notification for request {request_id}: {e}")
            await message.reply_text(
                f"Failed to fully complete fulfillment for request `{request_id}`. "
                "User might not have been notified. Please check logs."
            )

