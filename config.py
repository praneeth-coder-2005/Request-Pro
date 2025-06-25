# config.py
import os

API_ID = int(os.environ.get("API_ID", "YOUR_API_ID"))
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")

ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "YOUR_ADMIN_CHAT_ID")) # Your numerical user ID
MOVIE_CHANNEL_ID = int(os.environ.get("MOVIE_CHANNEL_ID", "YOUR_MOVIE_CHANNEL_ID")) # IMPORTANT: Numeric ID like -100123456789

# TMDB API Key
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "YOUR_TMDB_API_KEY")

# Logging level
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
