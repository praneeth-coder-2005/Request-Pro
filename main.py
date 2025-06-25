from pyrogram import Client, filters
from config import BOT_TOKEN, API_ID, API_HASH
from handlers import start

app = Client(
    "movie_request_bot",
    bot_token=BOT_TOKEN,
    api_id=API_ID,
    api_hash=API_HASH
)

@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    await start.handle_start(client, message)

if __name__ == "__main__":
    print("Bot is running...")
    app.run()
