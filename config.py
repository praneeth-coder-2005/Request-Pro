import os
from dotenv import load_dotenv

# Load environment variables from .env file (if running locally)
load_dotenv()

# Telegram Bot API Credentials
API_ID = int(os.getenv("API_ID", "22250562")) # Get from my.telegram.org
API_HASH = os.getenv("API_HASH", "07754d3bdc27193318ae5f6e6c8016af") # Get from my.telegram.org
BOT_TOKEN = os.getenv("BOT_TOKEN", "7549352926:AAGiDLjgMWBIH4VyuBCRHUfUkzCtx6bjlGg") # Get from @BotFather

# Admin User ID (Your Telegram User ID)
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "1894915577")) # Your Telegram User ID (numeric)

# Movie Channel ID (where movie files are stored)
# IMPORTANT: This must be the NUMERIC ID of your public/private channel (e.g., -100123456789)
# Your bot MUST be an administrator in this channel with 'Read Channel History' permission.
MOVIE_CHANNEL_ID = int(os.getenv("MOVIE_CHANNEL_ID", "-1002444091857")) # Example: -1001234567890

# TMDB API Key
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "bb5f40c5be4b24660cbdc20c2409835e") # Get from themoviedb.org
TMDB_BASE_URL = "https://api.themoviedb.org/3" 

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bot_data.db") # SQLite database file

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper() # INFO, DEBUG, WARNING, ERROR, CRITICAL
LOG_FILE = os.getenv("LOG_FILE", "bot.log")

# Bot name for messages (optional)
BOT_NAME = os.getenv("BOT_NAME", "Movie Request Bot")

# Timeout for user state (how long to remember user's last interaction for context)
STATE_TIMEOUT_SECONDS = int(os.getenv("STATE_TIMEOUT_SECONDS", "300")) # 5 minutes
