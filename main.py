from pyrogram import Client, filters
from config import BOT_TOKEN, API_ID, API_HASH
from handlers import start, request

app = Client(
    "movie_request_bot",
    bot_token=BOT_TOKEN,
    api_id=API_ID,
    api_hash=API_HASH
)

# Start command
@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    await start.handle_start(client, message)

# /request command
@app.on_message(filters.command("request") & filters.private)
async def request_command(client, message):
    await request.handle_request_command(client, message)

# Handle callback button from start message
@app.on_callback_query(filters.regex("request_movie"))
async def handle_request_button(client, callback_query):
    await callback_query.message.reply("🎬 Please type the movie name using /request <movie name>")

# Handle TMDb movie selection
@app.on_callback_query(filters.regex(r"select_movie_\d+"))
async def handle_movie_selection(client, callback_query):
    await request.handle_movie_selection(client, callback_query)

# Confirm or retry request
@app.on_callback_query(filters.regex(r"confirm_(yes|retry)_\d+"))
async def handle_confirmation(client, callback_query):
    await request.handle_confirmation(client, callback_query)

if __name__ == "__main__":
    print("Bot is running...")
    app.run()
