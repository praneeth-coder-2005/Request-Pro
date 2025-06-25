from pyrogram import Client, filters
from handlers.start import start_handler
from config import BOT_TOKEN, API_ID, API_HASH

app = Client(
    "movie_request_bot",
    bot_token=BOT_TOKEN,
    api_id=API_ID,
    api_hash=API_HASH
)

# Register handlers
app.add_handler(start_handler)

# Start the bot
if __name__ == "__main__":
    print("Bot is running...")
    app.run()
