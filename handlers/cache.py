from config import MOVIE_CHANNEL

# In-memory cache to store title -> message mapping
movie_file_cache = []

async def scan_and_store_file(msg):
    if not (msg.document or msg.video):
        return

    file_name = (
        msg.document.file_name if msg.document else msg.video.file_name
    ).lower()

    movie_file_cache.append({
        "file_name": file_name,
        "msg_id": msg.id
    })

async def deliver_file(client, query, title, quality):
    matched = []

    for movie in movie_file_cache:
        if title in movie["file_name"]:
            if quality in movie["file_name"]:
                matched.append(movie["msg_id"])

    if not matched:
        await query.message.reply("❌ No files found in that quality.")
        await query.answer()
        return

    for mid in matched:
        await client.copy_message(
            chat_id=query.message.chat.id,
            from_chat_id=MOVIE_CHANNEL,
            message_id=mid
        )

    await query.answer("✅ Sent!")
