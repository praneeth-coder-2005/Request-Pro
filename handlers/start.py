from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

async def send_welcome(client, message: Message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Request a Movie", callback_data="start_request")],
        [InlineKeyboardButton("📢 Updates", url="https://t.me/ClawMoviez")]
    ])

    await message.reply(
        "**👋 Welcome to Claw Movie Request Bot!**\n\n"
        "Request any movie and we’ll try to find it for you.",
        reply_markup=keyboard
    )
