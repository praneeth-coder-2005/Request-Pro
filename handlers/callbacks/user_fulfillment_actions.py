# handlers/callbacks/user_fulfillment_actions.py
import logging
from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode, ChatAction

from utils.database import get_user_state, clear_user_state, get_request_by_id, update_request_status, update_movie_channel_id
from config import MOVIE_CHANNEL_ID, ADMIN_CHAT_ID # Used for logging/admin notification

logger = logging.getLogger(__name__)

async def handle_user_select_quality_callback(client: Client, callback_query: CallbackQuery):
    """
    Handles the user's selection of a movie quality/version.
    Sends the selected movie file/link directly to the user.
    """
    parts = callback_query.data.split("_")
    request_id = int(parts[3]) # user_select_quality_<request_id>_<channel_msg_id>
    selected_channel_msg_id = int(parts[4])
    user_id = callback_query.from_user.id
    message = callback_query.message # The message with quality options

    state, state_data = await get_user_state(user_id)

    # Validate state and request ID
    if state != "awaiting_movie_quality_selection" or not state_data or state_data.get("request_id") != request_id:
        await message.edit_text("This selection is no longer valid or has expired. Please try requesting the movie again if needed.")
        await clear_user_state(user_id)
        logger.warning(f"User {user_id} tried to select quality for invalid state. State: {state}, Data: {state_data}")
        return

    request_data = await get_request_by_id(request_id)
    if not request_data:
        await message.edit_text("Error: Corresponding movie request not found. Please try requesting again.")
        await clear_user_state(user_id)
        logger.error(f"User {user_id} selected quality for request {request_id}, but request data not found.")
        return

    # Find the selected message details from the stored state data
    selected_option = next(
        (item for item in state_data.get("found_channel_options", []) if item["message_id"] == selected_channel_msg_id),
        None
    )

    if not selected_option:
        await message.edit_text("Selected movie version not found in the available options. Please try again or contact support.")
        logger.warning(f"User {user_id} selected missing option {selected_channel_msg_id} for request {request_id}.")
        return

    # Acknowledge selection and indicate sending
    await message.edit_text(f"Sending **{request_data['tmdb_title']}**... Please wait.")
    await client.send_chat_action(user_id, ChatAction.UPLOAD_DOCUMENT) # Or UPLOAD_VIDEO depending on file_type

    try:
        # Send the movie file/link directly to the user based on file_type
        if selected_option.get("is_media") and selected_option.get("file_id"):
            # Forward the message to send the file directly
            # This preserves file attributes, caption, etc.
            sent_message = await client.copy_message(
                chat_id=user_id,
                from_chat_id=MOVIE_CHANNEL_ID,
                message_id=selected_channel_msg_id,
                caption=f"🎬 **{request_data['tmdb_title']}**\n\n"
                        f"Enjoy your movie! ✨\n\n"
                        f"[Original Post in Channel]({selected_option['link']})" if selected_option['link'] else "Enjoy!",
                parse_mode=ParseMode.MARKDOWN
            )
            logger.info(f"User {user_id} received forwarded movie file for request {request_id}.")
        elif selected_option.get("file_type") == 'text_link' and selected_option.get("link"):
            # Send the direct link if it was a text-based link post
            await client.send_message(
                chat_id=user_id,
                text=f"🎬 **{request_data['tmdb_title']}**\n\n"
                     f"🔗 **Download Link:** [Click Here]({selected_option['link']})\n\n"
                     f"Enjoy your movie! ✨",
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=False # Allow preview for the link
            )
            logger.info(f"User {user_id} received manual link for request {request_id}.")
        else:
            await message.edit_text("Error: Could not retrieve the movie file/link details. Please try again or contact support.")
            logger.error(f"Failed to send movie to user {user_id} for request {request_id}. Missing file_id or link in options.")
            return

        # Update request status to 'fulfilled' only after successful delivery to user
        await update_request_status(request_id, "fulfilled", selected_option['link'])
        await update_movie_channel_id(request_id, selected_channel_msg_id)
        await clear_user_state(user_id) # Clear user's state after fulfillment

        # Update the user's original message with movie options - remove buttons
        await message.edit_reply_markup(reply_markup=None) # Remove selection buttons
        await message.edit_text(f"✅ Enjoy **{request_data['tmdb_title']}**! If you have any other requests, just use /request again.")


        # Update admin message to confirm fulfillment
        admin_message_id = request_data.get("admin_message_id")
        if admin_message_id:
            try:
                # Retrieve the admin message to keep its original content
                admin_msg = await client.get_messages(ADMIN_CHAT_ID, admin_message_id)
                original_caption_content = admin_msg.caption.split("\n\n✅ **Approved by Admin.**")[0] if admin_msg.caption and "\n\n✅ **Approved by Admin.**" in admin_msg.caption else admin_msg.caption

                await client.edit_message_caption(
                    chat_id=ADMIN_CHAT_ID,
                    message_id=admin_message_id,
                    caption=f"{original_caption_content}\n\n"
                            f"✅ **FULFILLED & INDEXED!**\n"
                            f"User **{callback_query.from_user.full_name}** selected quality.\n"
                            f"Channel Message ID: `{selected_channel_msg_id}`\n"
                            f"Link: [Original Post]({selected_option['link']})",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=None # Remove all buttons
                )
                logger.info(f"Admin message {admin_message_id} updated for request {request_id} after user selection.")
            except Exception as e:
                logger.warning(f"Could not update admin message {admin_message_id} after user fulfillment for request {request_id}: {e}")

    except Exception as e:
        logger.error(f"Error sending movie to user {user_id} for request {request_id}: {e}", exc_info=True)
        await message.edit_text("An error occurred while sending your movie. Please try again later or contact support.")
        # Do not clear state immediately, allow retry if transient error

