# config.py
import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

MOVIE_CHANNEL_ID = int(os.getenv("MOVIE_CHANNEL_ID")) # Your main movie channel
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID")) # Your personal chat ID

# TMDB API Key - Get this from https://www.themoviedb.org/settings/api
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

# Base URL for TMDB image
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500" # w500 is a good size
