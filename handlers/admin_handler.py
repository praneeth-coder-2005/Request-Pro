# handlers/admin_handler.py
from pyrogram import Client, filters
from pyrogram.types import Message
import logging

from config import ADMIN_CHAT_ID

logger = logging.getLogger(__name__)

# This handler now serves as a placeholder for general admin commands
# It no longer handles replies for movie fulfillment, as that's moved to auto-indexing.

@Client.on_message(filters.command("admin_status") & filters.user(ADMIN_CHAT_ID) & filters.private)
async def admin_status_command(client: Client, message: Message):
    """
    Example: A simple admin command to check bot status.
    """
    await message.reply_text("Bot is running normally. Auto-indexing feature is active. Remember to include #TMDB<ID> in channel posts.")
    logger.info(f"Admin {message.from_user.id} checked bot status.")

