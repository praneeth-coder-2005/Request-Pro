# handlers/admin_handler.py
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
import logging
import re # Used for finding request ID and URLs

# Import your database and config files
from utils.database import get_request_by_id, update_request_status
from config import ADMIN_CHAT_ID, MOVIE_CHANNEL_ID # Make sure ADMIN_CHAT_ID and MOVIE_CHANNEL_ID are correctly set in config.py

logger = logging.getLogger(__name__)

# This handles admin's replies to the bot's messages to upload files or links.
# It filters for private chats, replies, from the admin, and for documents, videos, or text.
@Client.on_message(filters.private & filters.reply & filters.user(ADMIN_CHAT_ID) & (filters.document | filters.video | filters.text))
async def handle_admin_upload_reply(client: Client, message: Message):
    """
    Handles admin's replies to the bot's fulfillment message,
    allowing them to upload files or send URLs to fulfill a request.
    """
    # Ensure the reply is actually to a message from the bot
    if not message.reply_to_message or not message.reply_to_message.from_user.is_bot:
        return

    # Try to find the Request ID in the message the admin replied to.
    # The request ID is usually in the caption or text of the bot's message in the format `ID: 123`
    match = re.search(r"ID: `(\d+)`", message.reply_to_message.caption or message.reply_to_message.text)
    if not match:
        logger.warning(f"Admin {message.from_user.id} replied to a bot message but couldn't find a valid Request ID.")
        # You could add a message here to guide the admin:
        # await message.reply_text("I couldn't find a valid request ID in the message you replied to. Please reply directly to the movie request message.")
        return

    request_id = int(match.group(1)) # Get the extracted request ID
    request_data = await get_request_by_id(request_id) # Get request details from DB

    # Check if the request exists and is in the 'approved_by_admin' state
    if not request_data or request_data["status"] != "approved_by_admin":
        await message.reply_text(
            f"This request (ID `{request_id}`) is not in a state to receive uploads. "
            "It might be already fulfilled or rejected."
        )
        logger.warning(f"Admin {message.from_user.id} tried to upload for request {request_id} which is not 'approved_by_admin'. Current status: {request_data['status'] if request_data else 'None'}")
        return

    tmdb_title = request_data["tmdb_title"]
    fulfilled_link = request_data.get("fulfilled_link", "") # Get any existing links for this request

    new_links = []
    if message.document: # If admin sent a file (document)
        try:
            # Forward the document to your movie channel
            forwarded_msg = await client.forward_messages(
                chat_id=MOVIE_CHANNEL_ID,
                from_chat_id=message.chat.id,
                message_ids=message.id,
                as_copy=True # Forward as a copy, not a true forward (hides "Forwarded from Admin")
            )
            link = forwarded_msg.link # Get the public link to the forwarded message in the channel
            new_links.append(link)
            await message.reply_text(f"File forwarded to channel. Link: {link}")
            logger.info(f"Admin {message.from_user.id} uploaded document for request {request_id}. Link: {link}")
        except Exception as e:
            await message.reply_text(f"Failed to forward document to channel: {e}")
            logger.error(f"Failed to forward document for request {request_id}: {e}")
            return
    elif message.video: # If admin sent a video
        try:
            # Forward the video to your movie channel
            forwarded_msg = await client.forward_messages(
                chat_id=MOVIE_CHANNEL_ID,
                from_chat_id=message.chat.id,
                message_ids=message.id,
                as_copy=True
            )
            link = forwarded_msg.link
            new_links.append(link)
            await message.reply_text(f"Video forwarded to channel. Link: {link}")
            logger.info(f"Admin {message.from_user.id} uploaded video for request {request_id}. Link: {link}")
        except Exception as e:
            await message.reply_text(f"Failed to forward video to channel: {e}")
            logger.error(f"Failed to forward video for request {request_id}: {e}")
            return
    elif message.text: # If admin sent text, check for URLs
        urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', message.text)
        if urls:
            new_links.extend(urls)
            await message.reply_text(f"Added URL(s): {', '.join(urls)}")
            logger.info(f"Admin {message.from_user.id} uploaded URL(s) for request {request_id}: {', '.join(urls)}")
        else:
            await message.reply_text("Please reply with a valid file, video, or URL.")
            logger.warning(f"Admin {message.from_user.id} replied with text for request {request_id} but no valid URLs found.")
            return
    else: # If unsupported file type was sent
        await message.reply_text("Unsupported file type. Please send a document, video, or a URL.")
        logger.warning(f"Admin {message.from_user.id} uploaded unsupported file type for request {request_id}.")
        return

    # Update the 'fulfilled_link' in the database with new and existing links
    current_links = fulfilled_link.split(',') if fulfilled_link else []
    updated_links = list(set(current_links + new_links)) # Combine and remove duplicates
    updated_fulfilled_link = ",".join(updated_links)

    success = await update_request_status(request_id, "approved_by_admin", updated_fulfilled_link)
    if success:
        await message.reply_text(
            f"Content for '{tmdb_title}' added. You can send more or click 'Fulfill (Done Uploading)'."
        )
        logger.info(f"Request {request_id} content updated by admin {message.from_user.id}. Current links: {updated_fulfilled_link}")
    else:
        await message.reply_text("Failed to update request with new content.")
        logger.error(f"Failed to update request {request_id} with content by admin {message.from_user.id}.")

