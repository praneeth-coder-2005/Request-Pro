# handlers/help_handler.py
from pyrogram import Client, filters
from pyrogram.types import Message
import logging

logger = logging.getLogger(__name__)

# This tells Pyrogram to run this function when a user sends "/help" in a private chat
@Client.on_message(filters.command("help") & filters.private)
async def help_command(client: Client, message: Message):
    """
    Handles the /help command by sending a list of commands.
    """
    logger.info(f"Received /help command from user {message.from_user.id}") # This will show in Colab logs
    help_text = (
        "Here are the commands you can use:\n\n"
        "🎬 `/request <movie name>` - Search for a movie and request it if not found.\n"
        "⚙️ `/start` - Get the welcome message.\n"
        "❓ `/help` - Show this help message.\n\n"
        "If you have any issues, please contact the bot admin."
    )
    await message.reply_text(help_text) # Send the help message back to the user

