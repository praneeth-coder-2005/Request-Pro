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
# IMPORTANT: Use a numeric ID (e.g., -100123456789) OR a public channel username (e.g., "@yourchannelname")
# If using a username, the bot must be able to access the channel and it MUST be a public channel.
MOVIE_CHANNEL_ID = os.getenv("MOVIE_CHANNEL_ID", "@dumprjddisb") # <<< MAKE SURE TO USE YOUR ACTUAL PUBLIC CHANNEL USERNAME HERE

# TMDB API Key
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "bb5f40c5be4b24660cbdc20c2409835e") # Get from themoviedb.org
TMDB_BASE_URL = "https://api.themoviedb.org/3" 

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./bot_data.db") # Changed to sqlite+aiosqlite

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper() # INFO, DEBUG, WARNING, ERROR, CRITICAL
LOG_FILE = os.getenv("LOG_FILE", "bot.log")

# Bot name for messages (optional)
BOT_NAME = os.getenv("BOT_NAME", "Movie Request Bot")

# Timeout for user state (how long to remember user's last interaction for context)
STATE_TIMEOUT_SECONDS = int(os.getenv("STATE_TIMEOUT_SECONDS", "300")) # 5 minutes
