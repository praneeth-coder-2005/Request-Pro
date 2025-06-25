from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery
from config import BOT_TOKEN, API_ID, API_HASH, UPDATE_CHANNEL
from handlers import start, request, delivery

app = Client(
    "movie_request_bot",
    bot_token=BOT_TOKEN,
    api_id=API_ID,
    api_hash=API_HASH
)

# /start handler (no update channel check)
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    await start.handle_start(client, message)
# /request handler
@app.on_message(filters.command("request") & filters.private)
async def request_handler(client: Client, message: Message):
    await request.handle_request_command(client, message)

# TMDB movie selection
@app.on_callback_query(filters.regex(r"select_movie_\d+"))
async def select_movie_handler(client: Client, callback_query: CallbackQuery):
    await request.handle_movie_selection(client, callback_query)

# Confirmation handler
@app.on_callback_query(filters.regex(r"confirm_(yes|retry)_\d+"))
async def confirm_handler(client: Client, callback_query: CallbackQuery):
    await request.handle_confirmation(client, callback_query)

# Movie quality filter trigger
@app.on_callback_query(filters.regex(r"deliver_movie_\d+"))
async def deliver_movie_handler(client: Client, callback_query: CallbackQuery):
    await delivery.handle_delivery(client, callback_query)

# Send files by quality
@app.on_callback_query(filters.regex(r"send_(1080p|720p|480p|others)_\d+"))
async def send_quality_files_handler(client: Client, callback_query: CallbackQuery):
    await delivery.handle_send_quality(client, callback_query)

if __name__ == "__main__":
    print("✅ Bot is running...")
    app.run()
from handlers.cache import scan_and_store_file

# Watch for uploads in file channel
@app.on_message(filters.channel & filters.chat(MOVIE_CHANNEL))
async def index_collector(client, message):
    await scan_and_store_file(message)
