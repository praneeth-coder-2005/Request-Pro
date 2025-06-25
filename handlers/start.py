from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

async def handle_start(client, message: Message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 Request Movie", callback_data="request_movie")],
        [InlineKeyboardButton("📃 How It Works", callback_data="how_it_works")],
        [InlineKeyboardButton("📢 Updates Channel", url="https://t.me/yourchannel")],
    ])

    welcome_text = f"""
👋 **Welcome {message.from_user.first_name}!**

🎬 I'm your Movie Request Bot!

✅ Features:
• Request any movie
• Track your requests
• Get fast admin replies

Stay tuned and enjoy!
    """

    await message.reply(welcome_text, reply_markup=keyboard)
