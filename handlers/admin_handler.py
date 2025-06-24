# handlers/admin_handler.py
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
import logging

from utils.database import get_request_by_id, update_request_status
from config import ADMIN_CHAT_ID, MOVIE_CHANNEL_ID

logger = logging.getLogger(__name__)

@Client.on_message(filters.private & filters.reply & filters.user(ADMIN_CHAT_ID) & (filters.document | filters.video | filters.text))
async def handle_admin_upload_reply(client: Client, message: Message):
    """
    Handles admin's replies to the bot's fulfillment message,
    allowing them to upload files or send URLs.
    """
    # Ensure the reply is to a message from the bot and contains 'Request ID: '
    if not message.reply_to_message or not message.reply_to_message.from_user.is_bot:
        return

    # Try to extract the request_id from the replied message's caption/text
    # We stored 'ID: `request_id`' in the admin message
    import re
    match = re.search(r"ID: `(\d+)`", message.reply_to_message.caption or message.reply_to_message.text)
    if not match:
        return # Not a reply to an admin request message

    request_id = int(match.group(1))
    request_data = await get_request_by_id(request_id)

    if not request_data or request_data["status"] != "approved_by_admin":
        await message.reply_text(
            f"This request (ID `{request_id}`) is not in a state to receive uploads. "
            "It might be already fulfilled or rejected."
        )
        return

    tmdb_title = request_data["tmdb_title"]
    user_id = request_data["user_id"]
    fulfilled_link = request_data.get("fulfilled_link", "") # Get existing links

    new_links = []
    if message.document:
        # Assuming you want to link to the uploaded file in your channel
        # Option 1: Forward to channel, then get permalink
        try:
            forwarded_msg = await client.forward_messages(
                chat_id=MOVIE_CHANNEL_ID,
                from_chat_id=message.chat.id,
                message_ids=message.id,
                as_copy=True # Important to get a new message ID in the target channel
            )
            link = forwarded_msg.link # Pyrogram provides this directly
            new_links.append(link)
            await message.reply_text(f"File forwarded to channel. Link: {link}")
        except Exception as e:
            await message.reply_text(f"Failed to forward document to channel: {e}")
            logger.error(f"Failed to forward document for request {request_id}: {e}")
            return
    elif message.video:
        try:
            forwarded_msg = await client.forward_messages(
                chat_id=MOVIE_CHANNEL_ID,
                from_chat_id=message.chat.id,
                message_ids=message.id,
                as_copy=True
            )
            link = forwarded_msg.link
            new_links.append(link)
            await message.reply_text(f"Video forwarded to channel. Link: {link}")
        except Exception as e:
            await message.reply_text(f"Failed to forward video to channel: {e}")
            logger.error(f"Failed to forward video for request {request_id}: {e}")
            return
    elif message.text:
        # Check if the text is a URL
        urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', message.text)
        if urls:
            new_links.extend(urls)
            await message.reply_text(f"Added URL(s): {', '.join(urls)}")
        else:
            await message.reply_text("Please reply with a valid file, video, or URL.")
            return
    else:
        await message.reply_text("Unsupported file type. Please send a document, video, or a URL.")
        return

    # Append new links to existing ones, de-duplicate, and update in DB
    current_links = fulfilled_link.split(',') if fulfilled_link else []
    updated_links = list(set(current_links + new_links)) # Use set for deduplication
    updated_fulfilled_link = ",".join(updated_links)

    success = await update_request_status(request_id, "approved_by_admin", updated_fulfilled_link) # Keep status as approved_by_admin
    if success:
        await message.reply_text(
            f"Content for '{tmdb_title}' added. You can send more or click 'Fulfill (Done Uploading)'."
        )
        logger.info(f"Admin uploaded content for request {request_id}. Current links: {updated_fulfilled_link}")
    else:
        await message.reply_text("Failed to update request with new content.")
        logger.error(f"Failed to update request {request_id} with content.")

