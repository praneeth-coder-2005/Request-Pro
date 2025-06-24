import asyncio
import logging
from pyrogram import Client
from loguru import logger as loguru_logger

from config import API_ID, API_HASH, BOT_TOKEN, LOG_LEVEL, LOG_FILE
from utils.database import init_db
from handlers.start_handler import start_command
from handlers.request_handler import request_command
from handlers.callback_handler import handle_callback_query
from handlers.admin_handler import admin_status_command # Example admin command

# Configure Loguru to handle logging
loguru_logger.add(
    LOG_FILE,
    rotation="10 MB",
    level=LOG_LEVEL,
    format="{time} {level} {message}",
    serialize=False # Set to True if you want JSON logs
)
logging.basicConfig(level=LOG_LEVEL) # Basic config for pyrogram's internal logging
logger = logging.getLogger(__name__) # Use standard logging for this file

async def main():
    """Initializes the bot and starts polling."""
    logger.info("Starting bot initialization...")

    # Initialize the database
    await init_db()
    logger.info("Database initialized.")

    # Create Pyrogram Client instance
    app = Client(
        "movie_request_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        workers=10 # Adjust as needed
    )
    logger.info("Pyrogram client created.")

    # Add handlers
    app.add_handler(start_command)
    app.add_handler(request_command)
    app.add_handler(handle_callback_query)
    app.add_handler(admin_status_command) # Add your admin command handler

    logger.info("Handlers added. Bot starting...")

    # Start the client
    await app.start()
    logger.info("Bot started successfully!")

    # Keep the bot running
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by KeyboardInterrupt.")
    except Exception as e:
        logger.error(f"Bot encountered a critical error: {e}", exc_info=True)

