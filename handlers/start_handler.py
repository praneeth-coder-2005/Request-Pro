%%writefile your_movie_bot/handlers/start_handler.py
from pyrogram import Client, filters
from pyrogram.types import Message
import logging

logger = logging.getLogger(__name__)

@Client.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    """Handles the /start command."""
    await message.reply_text(
        "Hello! I'm your Movie Request Bot. "
        "You can request movies by typing `/request <movie name>`. "
        "I'll search for it and let you know if it's available or when it is. "
        "Let's find some great movies for you! 🎬"
    )
    logger.info(f"User {message.from_user.id} used /start command.")

