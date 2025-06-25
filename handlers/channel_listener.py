# handlers/channel_listener.py
import logging
import re
import aiosqlite # Directly import aiosqlite for a specific query
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.enums import ParseMode

from utils.database import DB_NAME, update_request_status, update_movie_channel_id # Import DB_NAME and other functions
from config import MOVIE_CHANNEL_ID, ADMIN_CHAT_ID

logger = logging.getLogger(__name__)

# This handler listens for new messages in the designated movie channel
@Client.on_message(filters.chat(MOVIE_CHANNEL_ID) & (filters.media | filters.text))
async def auto_index_and_fulfill(client: Client, message: Message):
    """
    Automatically indexes new content posted in the movie channel
    and attempts to fulfill pending requests based on TMDB ID tags.
    """
    caption_text = message.caption or message.text
    if not caption_text:
        logger.debug(f"Message {message.id} in channel {MOVIE_CHANNEL_ID} has no caption/text. Skipping indexing.")
        return

    # Extract TMDB ID using regex from #TMDB<ID> format
    tmdb_id_match = re.search(r'#TMDB(\d+)', caption_text)
    if not tmdb_id_match:
        logger.debug(f"Message {message.id} in channel {MOVIE_CHANNEL_ID} has no #TMDB tag. Skipping auto-fulfillment.")
        return

    tmdb_id = int(tmdb_id_match.group(1))
    logger.info(f"Detected #TMDB{tmdb_id} in message {message.id} from channel {MOVIE_CHANNEL_ID}. Checking for pending requests.")

    # Get the permalink to the message in the channel
    fulfilled_link = message.link or f"https://t.me/{str(MOVIE_CHANNEL_ID).lstrip('-100')}/{message.id}"

    # Search for a *pending* movie request with this TMDB ID
    conn = await aiosqlite.connect(DB_NAME)
    async with conn.cursor() as cursor:
        await cursor.execute(
            "SELECT id, user_id, user_name, tmdb_id, tmdb_title, tmdb_overview, tmdb_poster_path, "
            "request_date, status, admin_message_id, original_user_request_msg_id, "
            "channel_message_id, fulfilled_link FROM movie_requests WHERE tmdb_id = ? AND status = 'pending' LIMIT 1",
            (tmdb_id,)
        )
        row = await cursor.fetchone()
    await conn.close()

    if row:
        columns = [description[0] for description in cursor.description]
        pending_request = dict(zip(columns, row))

        request_id = pending_request["id"]

        # Mark the request as fulfilled
        await update_request_status(request_id, "fulfilled", fulfilled_link)
        await update_movie_channel_id(request_id, message.id)

        logger.info(f"Pending request {request_id} for TMDB ID {tmdb_id} auto-fulfilled by channel message {message.id}.")

        # --- Notify the original user and update the admin's original request message ---
        user_id_to_notify = pending_request["user_id"]
        tmdb_title = pending_request["tmdb_title"]
        user_msg_id = pending_request.get("original_user_request_msg_id")
        original_admin_message_id = pending_request.get("admin_message_id")

        final_user_message_text = (
            f"🎉 Great news! Your requested movie, **{tmdb_title}**, is now available!\n\n"
            f"Click the button below to go directly to the movie in the channel.\n\n"
            f"Enjoy your movie! 🍿"
        )

        go_to_movie_url = fulfilled_link # Already prioritized in `fulfilled_link` variable

        user_reply_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Go to Movie 🎬", url=go_to_movie_url)]
        ])

        # Try to edit the user's original request message
        if user_msg_id:
            try:
                await client.edit_message_text(
                    chat_id=user_id_to_notify,
                    message_id=user_msg_id,
                    text=final_user_message_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=user_reply_keyboard
                )
                logger.info(f"User {user_id_to_notify}'s original message {user_msg_id} edited for request {request_id}.")
            except Exception as e:
                logger.warning(f"Could not edit original user message {user_msg_id} for user {user_id_to_notify}: {e}. Sending new message instead.")
                await client.send_message(
                    chat_id=user_id_to_notify,
                    text=final_user_message_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=user_reply_keyboard
                )
        else: # If original message ID wasn't stored or is null
            await client.send_message(
                chat_id=user_id_to_notify,
                text=final_user_message_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=user_reply_keyboard
            )
            logger.info(f"New message sent to user {user_id_to_notify} for request {request_id}.")

        # Update the admin's original approval message to reflect completion
        if original_admin_message_id:
            try:
                # Fetch the original caption before editing, to preserve it
                original_admin_message = await client.get_messages(ADMIN_CHAT_ID, original_admin_message_id)
                original_caption_content = original_admin_message.caption if original_admin_message.caption else ""

                await client.edit_message_caption(
                    chat_id=ADMIN_CHAT_ID,
                    message_id=original_admin_message_id,
                    caption=original_caption_content +
                            f"\n\n✅ **FULFILLED & INDEXED!**\n"
                            f"Channel Message ID: `{message.id}`\n"
                            f"Link: [Click Here]({go_to_movie_url})",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=None # Remove all buttons
                )
                logger.info(f"Admin message {original_admin_message_id} updated for request {request_id}.")
            except Exception as e:
                logger.warning(f"Could not edit original admin message {original_admin_message_id}: {e}")
                # Optionally send a new message to admin if edit fails
                await client.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=f"Fulfillment notification for request `{request_id}` sent to user. "
                         f"However, I couldn't update the original admin message {original_admin_message_id}. "
                         f"Movie Link: {go_to_movie_url}",
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True
                )
        # --- End of notification and admin message update ---

    else:
        logger.info(f"No pending request found for TMDB ID {tmdb_id}. Message {message.id} in channel {MOVIE_CHANNEL_ID} was posted but no active request matched it.")
        # Optional: You could still save this message to a `channel_index` table
        # if you want a complete index of all channel content, regardless of requests.
        # This is beyond the current scope but good for future enhancement.

