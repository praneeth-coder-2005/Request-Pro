from pyrogram import Client, filters
from config import BOT_TOKEN, API_ID, API_HASH
from handlers import start, request

app = Client("movie_request_bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    await start.send_welcome(client, message)

@app.on_callback_query(filters.regex("start_request"))
async def start_request_callback(client, callback_query):
    await callback_query.message.reply("Type the movie name using:\n\n`/request movie name`")
    await callback_query.answer()

@app.on_message(filters.command("request"))
async def request_cmd(client, message):
    await request.handle_request_command(client, message)

@app.on_callback_query(filters.regex(r"movie_\d+"))
async def movie_selected(client, callback_query):
    await request.handle_movie_selection(client, callback_query)

@app.on_callback_query(filters.regex(r"confirm_(yes|no).*"))
async def confirm_handler(client, callback_query):
    await request.handle_confirmation(client, callback_query)

app.run()
