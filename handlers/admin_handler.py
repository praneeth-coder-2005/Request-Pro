# handlers/admin_handler.py
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatAction, MessageMediaType, ParseMode
import logging
import re # For URL validation

from utils.database import get_user_state, clear_user_state, get_request_by_id, update_request_status, update_movie_channel_id
from config import ADMIN_CHAT_ID, MOVIE_CHANNEL_ID
from handlers.callbacks.admin_actions import notify_user_and_update_admin_message # Import the new helper

logger = logging.getLogger(__name__)

@Client.on_message(filters.private & filters.user(ADMIN_CHAT_ID) & filters.reply)
async def handle_admin_manual_link_reply(client: Client, message: Message):
    """
    Handles admin's reply message containing a direct download link
    after choosing 'Manually Input Link'.
    """
    user_id = message.from_user.id
    state, state_data = await get_user_state(user_id)

    # Ensure admin is in the correct state and replying to the bot's message
    if state == "awaiting_manual_link" and state_data and "request_id" in state_data:
        request_id = state_data["request_id"]
        request_data = await get_request_by_id(request_id)

        if not request_data:
            await message.reply_text("Error: Corresponding request not found. Please try approving again.")
            await clear_user_state(user_id)
            logger.error(f"Admin {user_id} replied for request {request_id}, but request data not found.")
            return

        fulfilled_link = message.text.strip()

        # Basic URL validation
        if not re.match(r'^https?://[^\s/$.?#].[^\s]*$', fulfilled_link):
            await message.reply_text("That doesn't look like a valid direct URL. Please provide a full URL starting with http:// or https://.")
            return # Don't clear state, let them retry

        await message.reply_text("Processing your link...")
        await client.send_chat_action(message.chat.id, ChatAction.TYPING)

        try:
            movie_title_for_channel = request_data.get("tmdb_title", "Requested Movie")
            movie_overview_for_channel = request_data.get("tmdb_overview", "No overview.")
            movie_release_date = request_data.get("release_date", "N/A")

            # Post the URL to the channel with movie info
            channel_caption = (
                f"🎬 **{movie_title_for_channel}**\n\n"
                f"🗓️ **Release:** {movie_release_date}\n"
                f"📝 **Overview:** {movie_overview_for_channel}\n\n"
                f"🔗 **Direct Link:** [Click here]({fulfilled_link})\n\n" # Inline link
                f"✨ Requested by user: [{request_data.get('user_name')}](tg://user?id={request_data.get('user_id')})"
                f"\n\n#Movie #Request #TMDB{request_data['tmdb_id']}" # Added TMDB tag for future search
            )

            channel_message = await client.send_message(
                chat_id=MOVIE_CHANNEL_ID,
                text=channel_caption,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=False # Allow Telegram to show preview for URLs
            )

            if channel_message:
                channel_msg_id = channel_message.id
                # Update request status and store the channel message ID and fulfilled link
                await update_request_status(request_id, "fulfilled", fulfilled_link)
                await update_movie_channel_id(request_id, channel_msg_id)
                await clear_user_state(user_id) # Clear admin's state

                await message.reply_text("Movie link posted and indexed! User will be notified.")

                # Notify the original user and update admin message
                await notify_user_and_update_admin_message(
                    client,
                    request_data,
                    channel_msg_id=channel_msg_id,
                    fulfilled_link=fulfilled_link
                )
                logger.info(f"Request {request_id} fulfilled by admin {user_id} with manual link: {fulfilled_link}.")

            else:
                logger.error(f"Failed to get channel_message object after sending URL for request {request_id}.")
                await message.reply_text("Failed to post URL to channel. No message object returned.")

        except Exception as e:
            logger.error(f"Critical error handling admin manual link for request {request_id}: {e}", exc_info=True)
            await message.reply_text(
                f"An unhandled error occurred during link posting/indexing: {e}. Please check logs."
            )
    else:
        logger.debug(f"Admin {user_id} replied but not in 'awaiting_manual_link' state. Ignoring or re-prompting.")
        # If the reply is not related to an awaited link, you might want to:
        # 1. Simply ignore (pass)
        # 2. Send a generic "I'm not expecting a link from you right now" message
        # For now, we'll just ignore if it's not a relevant state.
        pass

