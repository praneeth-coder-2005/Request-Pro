# handlers/start_handler.py
from pyrogram import Client, filters
from pyrogram.types import Message
import logging

logger = logging.getLogger(__name__)

@Client.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    """
    Handles the /start command.
    """
    logger.info(f"Received /start command from user {message.from_user.id}")
    user_mention = message.from_user.mention if message.from_user else "User"
    welcome_text = (
        f"Hello {user_mention}!\n\n"
        "I'm your Movie Request Bot. You can request movies that are not available "
        "in our channel.\n\n"
        "Use /request <movie name> to ask for a movie (e.g., `/request Inception`).\n"
        "Use /help to see more commands."
    )
    await message.reply_text(welcome_text)


