# config.py
import os

API_ID = int(os.environ.get("API_ID", "22250562"))
API_HASH = os.environ.get("API_HASH", "07754d3bdc27193318ae5f6e6c8016af")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "7549352926:AAGiDLjgMWBIH4VyuBCRHUfUkzCtx6bjlGg")

ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "1894915577")) # Your numerical user ID
MOVIE_CHANNEL_ID = int(os.environ.get("MOVIE_CHANNEL_ID", "-1002444091857")) # IMPORTANT: Numeric ID like -100123456789

# TMDB API Key
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "bb5f40c5be4b24660cbdc20c2409835e")

# Logging level
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
