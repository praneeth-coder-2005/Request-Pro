from pyrogram import Client, filters
from pyrogram.types import CallbackQuery

@Client.on_callback_query(filters.regex("get"))
async def deliver_file(client: Client, callback_query: CallbackQuery):
    _, msg_id, chat_id = callback_query.data.split("|")
    await callback_query.answer("📤 Sending file...")
    try:
        await client.copy_message(
            chat_id=callback_query.message.chat.id,
            from_chat_id=int(chat_id),
            message_id=int(msg_id)
        )
    except Exception as e:
        await callback_query.message.reply(f"❌ Failed to send file.\n\n{e}")
