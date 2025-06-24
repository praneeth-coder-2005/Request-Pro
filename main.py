# main.py
import asyncio
import logging
from pyrogram import Client
from pyrogram.types import BotCommand, BotCommandScopeAllPrivateChats

from config import API_ID, API_HASH, BOT_TOKEN, ADMIN_CHAT_ID, MOVIE_CHANNEL_ID
from utils.database import init_db

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# List of handler modules to import
HANDLER_MODULES = [
    "handlers.start_handler",
    "handlers.help_handler",
    "handlers.request_handler",
    "handlers.callback_handler", # Add new callback handler
    "handlers.admin_handler",     # Add new admin handler
]

async def set_bot_commands(client: Client):
    """Sets the bot's commands for a better user experience."""
    commands = [
        BotCommand("start", "Start the bot and get a welcome message"),
        BotCommand("help", "Get information about available commands"),
        BotCommand("request", "Request a movie not available in the channel"),
        BotCommand("myrequests", "View your pending movie requests"),
    ]
    # Set commands for private chats
    await client.set_bot_commands(commands, scope=BotCommandScopeAllPrivateChats())
    logger.info("Bot commands set successfully.")

async def main():
    """
    Main function to initialize and run the bot.
    """
    app = Client(
        "movie_request_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        plugins=dict(root="handlers")
    )

    logger.info("Starting bot...")

    await init_db()

    async with app:
        logger.info("Bot client initialized. Setting bot commands...")
        await set_bot_commands(app)
        logger.info("Bot started! Press Ctrl+C to stop.")
        await app.idle()
        logger.info("Bot stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
