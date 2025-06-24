import asyncio
import os
from loguru import logger as loguru_logger
from pyrogram import Client, idle
from pyrogram.errors import UsernameNotOccupied, PeerIdInvalid, RPCError

# Import configuration variables
from config import (
    API_ID, API_HASH, BOT_TOKEN, LOG_LEVEL, LOG_FILE,
    ADMIN_CHAT_ID, MOVIE_CHANNEL_ID, TMDB_API_KEY, TMDB_BASE_URL,
    DATABASE_URL, BOT_NAME, STATE_TIMEOUT_SECONDS
)

# Configure Loguru logger
loguru_logger.add(
    LOG_FILE,
    level=LOG_LEVEL,
    rotation="10 MB",
    compression="zip",
    enqueue=True,
    backtrace=True,
    diagnose=True
)

# Set up Pyrogram Client
app = Client(
    "movie_request_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# --- Import handlers after client is defined (if needed for circular imports) ---
# In this structure, it's fine to import them directly
from utils.database import init_db, set_user_state, get_user_state, clear_user_state, clear_all_expired_states
from utils.tmdb_api import search_movie_tmdb
from utils.channel_search import search_channel_messages, send_movie_post, get_movie_permalink
from handlers.start_command import start_command
from handlers.movie_request import movie_request_command, handle_movie_search_query
from handlers.callback_query import handle_callback_query
from handlers.admin_commands import admin_broadcast, admin_stats

# --- Register handlers ---
app.on_message(start_command, filters=~filters.bot & filters.private & filters.command("start"))
app.on_message(movie_request_command, filters=~filters.bot & filters.private & filters.command("request"))
app.on_message(handle_movie_search_query, filters=~filters.bot & filters.private & filters.text & ~filters.command(["start", "request"]))
app.on_callback_query(handle_callback_query)

# Admin commands (ensure they are restricted to ADMIN_CHAT_ID)
from pyrogram import filters
app.on_message(admin_broadcast, filters=filters.command("broadcast") & filters.user(ADMIN_CHAT_ID))
app.on_message(admin_stats, filters=filters.command("stats") & filters.user(ADMIN_CHAT_ID))


async def main():
    global MOVIE_CHANNEL_ID # Declare global to modify the variable from config

    try:
        loguru_logger.info("Initializing bot...")

        # --- Resolve MOVIE_CHANNEL_ID from username to numeric ID at startup ---
        if isinstance(MOVIE_CHANNEL_ID, str) and MOVIE_CHANNEL_ID.startswith('@'):
            loguru_logger.info(f"Resolving channel username: {MOVIE_CHANNEL_ID}")
            try:
                chat = await app.get_chat(MOVIE_CHANNEL_ID)
                if chat.type in ["channel", "supergroup"]:
                    # Update the global MOVIE_CHANNEL_ID variable with the resolved numeric ID
                    MOVIE_CHANNEL_ID = chat.id
                    loguru_logger.info(f"Resolved channel ID: {MOVIE_CHANNEL_ID}")
                else:
                    loguru_logger.error(f"Provided username '{MOVIE_CHANNEL_ID}' is not a channel or supergroup. Found type: {chat.type}")
                    raise ValueError(f"Invalid channel username type: {chat.type}")
            except (UsernameNotOccupied, PeerIdInvalid):
                loguru_logger.critical(f"Channel username '{MOVIE_CHANNEL_ID}' not found or is invalid. Please check the username in config.py.")
                await app.stop()
                return
            except RPCError as e:
                loguru_logger.critical(f"Telegram API error while resolving username '{MOVIE_CHANNEL_ID}': {e}")
                await app.stop()
                return
            except Exception as e:
                loguru_logger.critical(f"An unexpected error occurred while resolving username '{MOVIE_CHANNEL_ID}': {e}", exc_info=True)
                await app.stop()
                return
        elif not isinstance(MOVIE_CHANNEL_ID, int):
            # If it's not a username, but also not an int, try converting
            try:
                MOVIE_CHANNEL_ID = int(MOVIE_CHANNEL_ID)
                loguru_logger.info(f"Using numeric channel ID: {MOVIE_CHANNEL_ID}")
            except ValueError:
                loguru_logger.critical(f"MOVIE_CHANNEL_ID is neither a valid numeric ID nor a resolvable username: {MOVIE_CHANNEL_ID}")
                await app.stop()
                return
        else:
            loguru_logger.info(f"Using pre-configured numeric channel ID: {MOVIE_CHANNEL_ID}")
        # --- End of channel ID resolution ---

        await init_db() # Initialize database

        loguru_logger.info("Bot starting...")
        await app.start()
        loguru_logger.info("Bot started!")

        # Start background task to clear expired states
        asyncio.create_task(clear_all_expired_states())

        await idle() # Keep the bot running until interrupted
        loguru_logger.info("Bot stopping...")
        await app.stop()
        loguru_logger.info("Bot stopped.")

    except Exception as e:
        loguru_logger.critical(f"An error occurred during bot startup: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())

