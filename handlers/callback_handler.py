# handlers/callback_handler.py
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Message
import asyncio
import logging

from utils.tmdb_api import get_movie_details_tmdb, get_tmdb_image_url
from utils.database import get_user_state, clear_user_state, add_movie_request, update_request_status, get_request_by_id, update_request_admin_message_id
from utils.helpers import search_channel_for_movie, clean_movie_title, format_movie_info
from config import MOVIE_CHANNEL_ID, ADMIN_CHAT_ID

logger = logging.getLogger(__name__)

@Client.on_callback_query()
async def handle_callback_query(client: Client, callback_query: CallbackQuery):
    data = callback_query.data
    user_id = callback_query.from_user.id
    message = callback_query.message

    await callback_query.answer() # Acknowledge the callback immediately

    # --- User TMDB Selection ---
    if data.startswith("select_tmdb_"):
        state, state_data = await get_user_state(user_id)
        if state != "awaiting_tmdb_selection" or not state_data or "tmdb_results" not in state_data:
            await message.edit_text("This selection is no longer valid. Please start a new `/request`.")
            await clear_user_state(user_id)
            return

        selected_index = int(data.split("_")[2])
        tmdb_results = state_data["tmdb_results"]

        if selected_index >= len(tmdb_results):
            await message.edit_text("Invalid selection. Please try again.")
            return

        selected_movie = tmdb_results[selected_index]
        tmdb_id = selected_movie["id"]
        tmdb_title = selected_movie["title"]

        # Get full details from TMDB to ensure we have the best info
        full_movie_details = await get_movie_details_tmdb(tmdb_id)
        if not full_movie_details:
            await message.edit_text("Could not retrieve full movie details. Please try again or search for a different movie.")
            await clear_user_state(user_id)
            return

        formatted_info = format_movie_info(full_movie_details)
        poster_url = get_tmdb_image_url(full_movie_details.get("poster_path"))

        # Store the selected movie data for confirmation
        await set_user_state(user_id, "awaiting_confirmation", {"movie_data": full_movie_details})

        # Ask for confirmation with rich info
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
                    parse_mode="markdown",
                    disable_web_page_preview=True # Disable preview if no poster
                )
        except Exception as e:
            logger.error(f"Error editing message with TMDB info for user {user_id}: {e}")
            await message.edit_text(
                f"Is this the movie you are looking for?\n\n{formatted_info}\n\n"
                "I couldn't display the poster. Please confirm manually.",
                reply_markup=confirmation_keyboard,
                parse_mode="markdown",
                disable_web_page_preview=True
            )
        logger.info(f"User {user_id} selected TMDB ID {tmdb_id}, awaiting confirmation.")

    elif data == "tmdb_none_correct":
        await message.edit_text(
            "Okay, if none of those were correct, please try a different /request with a more specific title."
        )
        await clear_user_state(user_id)
        logger.info(f"User {user_id} indicated none of TMDB results were correct.")

    elif data.startswith("confirm_request_"):
        state, state_data = await get_user_state(user_id)
        if state != "awaiting_confirmation" or not state_data or "movie_data" not in state_data:
            await message.edit_text("This confirmation is no longer valid. Please start a new `/request`.")
            await clear_user_state(user_id)
            return

        confirmed = data.split("_")[2] == "true"
        movie_data = state_data["movie_data"]

        await clear_user_state(user_id) # Clear state after user's decision

        if not confirmed:
            await message.edit_text("Okay, let's try again. Please use `/request` with a different title.")
            logger.info(f"User {user_id} cancelled confirmation for {movie_data.get('title')}.")
            return

        # User confirmed the movie. Now proceed with channel search or admin request.
        await message.edit_text("Thanks for confirming! Checking our channel now...")
        await client.send_chat_action(message.chat.id, ChatAction.TYPING)

        # 1. Check if movie is already in the channel
        cleaned_tmdb_title = clean_movie_title(movie_data.get("title"))
        found_movie_message = await search_channel_for_movie(
            client, MOVIE_CHANNEL_ID, cleaned_tmdb_title
        )

        if found_movie_message:
            # Movie found, send it to the user
            try:
                await client.copy_message(
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
                await message.edit_text(
                    "I found the movie, but encountered an error sending it. "
                    "Please try again later or contact support."
                )
                logger.error(f"Error sending found movie to {user_id}: {e}")
        else:
            # Movie not found, send to admin and record
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
                await message.edit_text(
                    "An error occurred while processing your request. Please try again."
                )
                return

            # Forward request to admin with rich info and action buttons
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
                admin_msg = await client.send_photo(
                    chat_id=ADMIN_CHAT_ID,
                    photo=poster_url if poster_url else "https://via.placeholder.com/500x750?text=No+Poster", # Fallback image
                    caption=admin_message_caption,
                    parse_mode="markdown",
                    reply_markup=admin_keyboard
                )
            except Exception as e:
                logger.error(f"Error sending TMDB photo to admin {ADMIN_CHAT_ID}: {e}")
                admin_msg = await client.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=admin_message_caption + "\n(Poster failed to load)",
                    parse_mode="markdown",
                    reply_markup=admin_keyboard,
                    disable_web_page_preview=True
                )

            await update_request_admin_message_id(request_id, admin_msg.id)

            # Notify user
            await message.edit_text(
                f"⏳ Your request for **{movie_data.get('title')}** has been submitted! "
                "It's not yet available in our channel. We've forwarded it to the admin "
                "and will notify you within 12 hours once it's uploaded. Thank you for your patience! 🙏",
                parse_mode="markdown"
            )
            logger.info(f"User {user_id} requested '{movie_data.get('title')}' (TMDB ID {movie_data.get('id')}), forwarded to admin.")

    # --- Admin Action Callbacks ---
    elif data.startswith("admin_approve_"):
        request_id = int(data.split("_")[2])
        request_data = await get_request_by_id(request_id)

        if not request_data or request_data["status"] != "pending":
            await message.edit_text(f"Request ID `{request_id}` is not pending or does not exist.")
            return

        # Update status to a temporary 'approved_by_admin' to await files
        await update_request_status(request_id, "approved_by_admin")

        # Edit admin message with next steps
        await message.edit_reply_markup(reply_markup=None) # Remove old buttons
        await message.edit_caption(
            caption=message.caption + "\n\n✅ **Approved by Admin.**\n\n"
                    "Now, please use the buttons below to upload the movie files/links. "
                    "You can send multiple files/links if needed.",
            parse_mode="markdown",
            reply_markup=InlineKeyboardMarkup([
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
            return

        await update_request_status(request_id, "rejected")
        await message.edit_reply_markup(reply_markup=None) # Remove old buttons
        await message.edit_caption(
            caption=message.caption + "\n\n❌ **Request Rejected by Admin.**",
            parse_mode="markdown"
        )
        # Notify user about rejection (optional, but good UX)
        try:
            await client.send_message(
                chat_id=request_data["user_id"],
                text=f"🙁 We're sorry, your request for **{request_data['tmdb_title']}** could not be fulfilled at this time. "
                     "Please try again later or request a different movie.",
                parse_mode="markdown"
            )
        except Exception as e:
            logger.warning(f"Failed to notify user {request_data['user_id']} about rejected request {request_id}: {e}")
        logger.info(f"Admin rejected request {request_id}.")

    # These buttons don't do much on click, they just guide the admin to reply
    elif data.startswith("admin_upload_files_") or data.startswith("admin_upload_url_"):
        request_id = int(data.split("_")[2])
        # Just provide feedback that admin needs to reply
        await callback_query.answer("Please reply to THIS message with the files or URL(s).")
        logger.info(f"Admin clicked upload button for request {request_id}. Awaiting reply.")

    elif data.startswith("admin_complete_fulfillment_"):
        request_id = int(data.split("_")[3])
        request_data = await get_request_by_id(request_id)

        if not request_data or request_data["status"] not in ("approved_by_admin", "fulfilled"):
            await message.edit_text(f"Request ID `{request_id}` is not in a fulfillable state.")
            return

        # Get fulfilled_link (could be multiple if comma-separated, or just a placeholder)
        # For simplicity, we'll use a placeholder 'Done' if no link was explicitly set
        fulfilled_link = request_data.get("fulfilled_link", "Uploaded to channel.")

        await update_request_status(request_id, "fulfilled", fulfilled_link)

        # Notify the user (using the original user message if possible)
        user_id_to_notify = request_data["user_id"]
        tmdb_title = request_data["tmdb_title"]
        user_msg_id = request_data.get("original_user_request_msg_id")

        try:
            final_user_message_text = (
                f"🎉 Great news! Your requested movie, **{tmdb_title}**, is now available!\n\n"
            )
            if fulfilled_link and fulfilled_link != "Uploaded to channel.":
                 final_user_message_text += f"Click here to watch: {fulfilled_link}\n\n"
                 # If you expect multiple links, you'd parse them here and list them
            else:
                 final_user_message_text += f"It has been uploaded to our main channel.\n\n"
                 f"You can search for it in {client.get_chat(MOVIE_CHANNEL_ID).title if MOVIE_CHANNEL_ID else 'the main channel'} or click the button below.\n\n"

            final_user_message_text += "Enjoy your movie! 🍿"

            # Try to edit the user's original request message if possible, otherwise send new
            if user_msg_id:
                try:
                    # If you had sent a photo with the original request, edit photo.
                    # This example assumes the original user message was text.
                    await client.edit_message_text(
                        chat_id=user_id_to_notify,
                        message_id=user_msg_id,
                        text=final_user_message_text,
                        parse_mode="markdown",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("Go to Movie 🎬", url=fulfilled_link if fulfilled_link != "Uploaded to channel." else "https://t.me/yourchannel")]
                        ]) if fulfilled_link else None
                    )
                except Exception as e:
                    logger.warning(f"Could not edit original user message {user_msg_id} for user {user_id_to_notify}: {e}. Sending new message.")
                    await client.send_message(
                        chat_id=user_id_to_notify,
                        text=final_user_message_text,
                        parse_mode="markdown",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("Go to Movie 🎬", url=fulfilled_link if fulfilled_link != "Uploaded to channel." else "https://t.me/yourchannel")]
                        ]) if fulfilled_link else None
                    )
            else:
                await client.send_message(
                    chat_id=user_id_to_notify,
                    text=final_user_message_text,
                    parse_mode="markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("Go to Movie 🎬", url=fulfilled_link if fulfilled_link != "Uploaded to channel." else "https://t.me/yourchannel")]
                    ]) if fulfilled_link else None
                )

            # Final update to admin message
            await message.edit_caption(
                caption=message.caption + f"\n\n✅ **Fulfillment Complete!** Notified user. Link: {fulfilled_link}",
                parse_mode="markdown",
                reply_markup=None # Remove all buttons
            )
            logger.info(f"Request {request_id} for '{tmdb_title}' fully fulfilled and user notified.")

        except Exception as e:
            logger.error(f"Error during final user notification for request {request_id}: {e}")
            await message.reply_text(
                f"Failed to fully complete fulfillment for request `{request_id}`. "
                "User might not have been notified. Please check logs."
            )

