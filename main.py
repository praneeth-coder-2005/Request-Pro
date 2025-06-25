from pyrogram import Client, filters
from pyrogram.types import Message

app = Client(
    "movie_request_bot",
    bot_token="7549352926:AAGiDLjgMWBIH4VyuBCRHUfUkzCtx6bjlGg",
    api_id=22250562,
    api_hash="07754d3bdc27193318ae5f6e6c8016af"
)

@app.on_message(filters.private)
async def echo(client, message: Message):
    print("Message received!")
    await message.reply("✅ Bot is working!")

if __name__ == "__main__":
    print("Bot is running...")
    app.run()
