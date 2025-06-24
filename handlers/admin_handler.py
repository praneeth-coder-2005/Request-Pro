%%writefile your_movie_bot/handlers/admin_handler.py
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from config import ADMIN_CHAT_ID # Make sure ADMIN_CHAT_ID is imported

logger = logging.getLogger(__name__)

@Client.on_message(filters.command("admin_status") & filters.private)
async def admin_status_command(client: Client, message: Message):
    """
    Handles the /admin_status command.
    Only accessible by the ADMIN_CHAT_ID.
    """
    if message.from_user.id != ADMIN_CHAT_ID:
        await message.reply_text("You are not authorized to use this command.")
        logger.warning(f"Unauthorized access to /admin_status from user {message.from_user.id}.")
        return

    await message.reply_text(
        "Hello, Admin! Your bot is running.\n\n"
        "You can manage movie requests through the messages forwarded to this chat."
    )
    logger.info(f"Admin {message.from_user.id} checked bot status.")

