# main.py
import asyncio
import logging
import os
from pyrogram import Client, filters
from pyrogram.enums import ParseMode

from config import API_ID, API_HASH, BOT_TOKEN, LOG_LEVEL, ADMIN_CHAT_ID, MOVIE_CHANNEL_ID
from utils.database import init_db

# Configure logging
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Pyrogram Client
app = Client(
    "movie_request_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.MARKDOWN # Set default parse mode for the client
)

async def main():
    logger.info("Starting bot...")
    await init_db() # Initialize the database

    # Import handlers
    from handlers.start_handler import start_command
    from handlers.request_handler import handle_movie_request_command
    from handlers.callback_handler import handle_callback_query
    from handlers.help_handler import help_command
    from handlers.admin_handler import admin_status_command # Example admin command (now only this in admin_handler)
    from handlers.channel_listener import auto_index_and_fulfill # NEW: Import the channel listener

    # Add handlers
    app.add_handler(start_command)
    app.add_handler(handle_movie_request_command)
    app.add_handler(help_command)
    app.add_handler(handle_callback_query)

    # Admin related handlers
    app.add_handler(admin_status_command) # Add the example admin command
    app.add_handler(auto_index_and_fulfill) # NEW: Add the channel listener for auto-indexing

    try:
        async with app:
            logger.info("Bot started and listening for updates...")
            # Keep the bot running indefinitely
            await asyncio.Event().wait()
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True) # Added exc_info for full traceback
    finally:
        logger.info("Bot stopped.")

if __name__ == "__main__":
    asyncio.run(main())
