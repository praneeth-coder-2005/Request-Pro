from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# START handler
@Client.on_message(filters.command("start") & filters.private)
async def start_handler(client, message: Message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 Request Movie", callback_data="request_movie")],
        [InlineKeyboardButton("📃 How It Works", callback_data="how_it_works")],
        [InlineKeyboardButton("📢 Updates Channel", url="https://t.me/yourchannel")],
    ])

    welcome_text = f"""
👋 **Welcome {message.from_user.first_name}!**

🎬 I'm a powerful **Movie Request Bot** that helps you:
• Request your favorite movies
• Get fast responses from admins
• Track requested movies

Stay tuned and enjoy the experience!
    """

    await message.reply(welcome_text, reply_markup=keyboard)
