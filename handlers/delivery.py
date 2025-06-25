from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config import MOVIE_CHANNEL
from .request import movie_cache

# Handle user clicking '✅ Yes'
async def handle_delivery(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    movie_index = int(callback_query.data.split("_")[-1])
    movie_list = movie_cache.get(user_id)

    if not movie_list or movie_index >= len(movie_list):
        await callback_query.answer("❌ Movie not found in cache.", show_alert=True)
        return

    movie = movie_list[movie_index]
    title = movie["title"].lower()

    found_files = {"480p": [], "720p": [], "1080p": [], "others": []}

    async for msg in client.search_messages(chat_id=MOVIE_CHANNEL, query=title, limit=20):
        if not (msg.document or msg.video):
            continue

        file_name = (msg.document.file_name if msg.document else msg.video.file_name) or ""
        text = file_name.lower()

        if "480" in text:
            found_files["480p"].append(msg)
        elif "720" in text:
            found_files["720p"].append(msg)
        elif "1080" in text:
            found_files["1080p"].append(msg)
        else:
            found_files["others"].append(msg)

    if not any(found_files.values()):
        await callback_query.message.reply("❌ This movie is not available in our files yet.")
        await callback_query.answer()
        return

    # Quality selection buttons
    buttons = []
    for quality in ["1080p", "720p", "480p", "others"]:
        if found_files[quality]:
            buttons.append([
                InlineKeyboardButton(f"{quality.upper()} ({len(found_files[quality])})", callback_data=f"send_{quality}_{movie_index}")
            ])

    await callback_query.message.reply(
        f"🎬 **Select quality for:** `{movie['title']}`",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    await callback_query.answer()

# Handle sending selected quality files
async def handle_send_quality(client, callback_query: CallbackQuery):
    quality, index = callback_query.data.split("_")[1:]
    movie_index = int(index)
    user_id = callback_query.from_user.id

    movie_list = movie_cache.get(user_id)
    if not movie_list or movie_index >= len(movie_list):
        await callback_query.answer("❌ Movie not found in cache.", show_alert=True)
        return

    title = movie_list[movie_index]["title"].lower()

    found_files = {"480p": [], "720p": [], "1080p": [], "others": []}

    async for msg in client.search_messages(chat_id=MOVIE_CHANNEL, query=title, limit=20):
        if not (msg.document or msg.video):
            continue

        file_name = (msg.document.file_name if msg.document else msg.video.file_name) or ""
        text = file_name.lower()

        if "480" in text:
            found_files["480p"].append(msg)
        elif "720" in text:
            found_files["720p"].append(msg)
        elif "1080" in text:
            found_files["1080p"].append(msg)
        else:
            found_files["others"].append(msg)

    if not found_files[quality]:
        await callback_query.message.reply("❌ Files not available in selected quality.")
        await callback_query.answer()
        return

    for msg in found_files[quality]:
        await msg.copy(chat_id=callback_query.message.chat.id)

    await callback_query.answer("✅ Delivered files!")
