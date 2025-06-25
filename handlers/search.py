from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from db import get_files_by_title, get_files_by_title_and_lang

LANGUAGES = ["Telugu", "Hindi", "Tamil", "Malayalam", "English"]

@Client.on_message(filters.command("request"))
async def request_movie(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply("❌ Please enter a movie name.\n\nUsage: /request Movie Name")

    query = " ".join(message.command[1:])
    results = get_files_by_title(query)

    if not results:
        return await message.reply("❌ No results found.")

    reply_text = f"<b>🎬 Results for:</b> {query}\n\n"
    lang_set = set([res['language'] for res in results if res['language']])
    keyboard = [[InlineKeyboardButton(lang, callback_data=f"langfilter|{query}|{lang}")]
                for lang in sorted(lang_set)]
    for res in results[:10]:
        btn_text = f"[{res['file_size']}] {res['title']} ({res['language']})"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"get|{res['message_id']}|{res['channel_id']}")])
    await message.reply(reply_text, reply_markup=InlineKeyboardMarkup(keyboard))

@Client.on_callback_query(filters.regex("langfilter"))
async def lang_filter_handler(client, callback_query):
    _, title, lang = callback_query.data.split("|")
    results = get_files_by_title_and_lang(title, lang)
    if not results:
        return await callback_query.answer("No results in this language.", show_alert=True)

    reply_text = f"<b>🎬 Results for:</b> {title}\n🔤 Language: {lang}\n\n"
    keyboard = []
    for res in results[:10]:
        btn_text = f"[{res['file_size']}] {res['title']} ({res['language']})"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"get|{res['message_id']}|{res['channel_id']}")])
    await callback_query.message.edit_text(reply_text, reply_markup=InlineKeyboardMarkup(keyboard))
