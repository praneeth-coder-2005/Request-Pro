import asyncio
import logging
from pyrogram import Client
from pyrogram.types import BotCommand, BotCommandScopeAllPrivateChats

# Import your configuration variables
from config import API_ID, API_HASH, BOT_TOKEN, ADMIN_CHAT_ID, MOVIE_CHANNEL_ID
# Import your database initialization
from utils.database import init_db

# Basic logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# List of handler modules to import (Pyrogram will load these as plugins)
HANDLER_MODULES = [
    "handlers.start_handler",
    "handlers.help_handler",
    "handlers.request_handler",
    "handlers.callback_handler",
    "handlers.admin_handler",
    # Make sure all your handler files (start_handler.py, help_handler.py, etc.)
    # are present in the 'handlers' folder and are named correctly.
]

async def set_bot_commands(client: Client):
    """Sets the bot's commands for a better user experience."""
    commands = [
        BotCommand("start", "Start the bot and get a welcome message"),
        BotCommand("help", "Get information about available commands"),
        BotCommand("request", "Request a movie not available in the channel"),
        BotCommand("myrequests", "View your pending movie requests"),
    ]
    # Set commands for private chats only
    await client.set_bot_commands(commands, scope=BotCommandScopeAllPrivateChats())
    logger.info("Bot commands set successfully.")

async def main():
    """
    Main function to initialize and run the bot.
    """
    # Initialize the Pyrogram Client
    app = Client(
        "movie_request_bot",  # This name is used for the .session file
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        plugins=dict(root="handlers") # This tells Pyrogram to load all .py files in the 'handlers' directory
    )

    logger.info("Starting bot...")

    # Initialize the database (create tables if they don't exist)
    await init_db()

    # Start the Pyrogram client
    async with app:
        logger.info("Bot client initialized. Setting bot commands...")
        await set_bot_commands(app) # Set the commands in Telegram
        logger.info("Bot started! Press Ctrl+C to stop.")

        # This loop keeps the bot running indefinitely while listening for updates.
        # Pyrogram's event loop will handle incoming messages and callbacks.
        # It replaces the deprecated app.idle() for Pyrogram 2.x
        while True:
            await asyncio.sleep(1) # Sleep briefly to prevent busy-waiting and allow event loop to process

    # This part of the code below will only be reached if the bot process is explicitly stopped
    logger.info("Bot stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")

