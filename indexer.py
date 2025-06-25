from pyrogram import Client
from pymongo import MongoClient
import os

from config import API_ID, API_HASH, BOT_TOKEN, MONGODB_URI

client = MongoClient(MONGODB_URI)
db = client["moviebot"]
collection = db["files"]

MOVIE_CHANNEL = "dumprjddisb"  # Without @

def human_readable_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"

def parse_filename(name):
    parts = name.replace("_", ".").split(".")
    title = []
    language = "Unknown"
    for part in parts:
        if part.lower() in ["telugu", "hindi", "tamil", "malayalam", "english"]:
            language = part.capitalize()
        else:
            title.append(part)
    return " ".join(title).strip(), language

app = Client("indexer", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message()
async def index_all():
    async with app:
        print("⚙️ Starting Indexing...")
        async for msg in app.get_chat_history(MOVIE_CHANNEL):
            media = msg.document or msg.video
            if not media:
                continue

            file_name = media.file_name or "Unknown"
            file_size = human_readable_size(media.file_size)
            title, language = parse_filename(file_name)

            if collection.find_one({"message_id": msg.message_id}):
                continue

            doc = {
                "title": title,
                "file_name": file_name,
                "file_size": file_size,
                "language": language,
                "channel_id": msg.chat.id,
                "message_id": msg.message_id
            }
            collection.insert_one(doc)
            print(f"✅ Indexed: {file_name}")
        print("🎉 Indexing Completed.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(index_all())
