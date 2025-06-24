# handlers/admin_handler.py
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatAction, MessageMediaType, ParseMode # ADDED ParseMode here
import logging

from utils.database import get_user_state, clear_user_state, get_request_by_id, update_request_status, update_movie_channel_id
from config import ADMIN_CHAT_ID, MOVIE_CHANNEL_ID
from utils.helpers import format_movie_info # Still useful for initial admin message

logger = logging.getLogger(__name__)

@Client.on_message(filters.private & filters.user(ADMIN_CHAT_ID) & filters.reply)
async def handle_admin_upload_reply(client: Client, message: Message):
    """
    Handles admin's reply message containing the movie file or URL
    after approving a request.
    """
    user_id = message.from_user.id
    state, state_data = await get_user_state(user_id)

    # Ensure admin is in the correct state and replying to the bot's message
    if state == "awaiting_admin_upload" and state_data and "request_id" in state_data:
        request_id = state_data["request_id"]
        request_data = await get_request_by_id(request_id)

        if not request_data:
            await message.reply_text("Error: Corresponding request not found. Please try approving again.")
            await clear_user_state(user_id)
            logger.error(f"Admin {user_id} replied for request {request_id}, but request data not found.")
            return

        await message.reply_text("Processing your upload...")
        await client.send_chat_action(message.chat.id, ChatAction.UPLOAD_DOCUMENT)

        channel_msg_id = None
        fulfilled_link = None
        uploaded_successfully = False

        movie_title_for_channel = request_data.get("tmdb_title", "Requested Movie")
        movie_overview_for_channel = request_data.get("tmdb_overview", "No overview.")
        movie_release_date = request_data.get("release_date", "N/A")
        poster_path = request_data.get("tmdb_poster_path")

        # Prepare the caption for the channel post
        channel_caption = (
            f"🎬 **{movie_title_for_channel}**\n\n"
            f"🗓️ **Release:** {movie_release_date}\n"
            f"📝 **Overview:** {movie_overview_for_channel}\n\n"
            f"✨ Requested by user: [{request_data.get('user_name')}](tg://user?id={request_data.get('user_id')})"
            f"\n\n#Movie #Request" # Example hashtags
        )
        poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None

        try:
            if message.photo or message.video or message.document:
                # Admin sent a file
                logger.info(f"Admin {user_id} sent a file for request {request_id}. Uploading to channel {MOVIE_CHANNEL_ID}.")

                # Determine media type and ID
                media = None
                media_type = None
                if message.photo:
                    media = message.photo.file_id
                    media_type = MessageMediaType.PHOTO
                elif message.video:
                    media = message.video.file_id
                    media_type = MessageMediaType.VIDEO
                elif message.document:
                    media = message.document.file_id
                    media_type = MessageMediaType.DOCUMENT

                if not media:
                    await message.reply_text("Unsupported media type received. Please send a photo, video, or document.")
                    return

                # Send the file to the movie channel
                channel_message = None
                if media_type == MessageMediaType.PHOTO:
                    channel_message = await client.send_photo(
                        chat_id=MOVIE_CHANNEL_ID,
                        photo=media,
                        caption=channel_caption,
                        parse_mode=ParseMode.MARKDOWN # FIXED
                    )
                elif media_type == MessageMediaType.VIDEO:
                    channel_message = await client.send_video(
                        chat_id=MOVIE_CHANNEL_ID,
                        video=media,
                        caption=channel_caption,
                        parse_mode=ParseMode.MARKDOWN # FIXED
                    )
                elif media_type == MessageMediaType.DOCUMENT:
                    channel_message = await client.send_document(
                        chat_id=MOVIE_CHANNEL_ID,
                        document=media,
                        caption=channel_caption,
                        parse_mode=ParseMode.MARKDOWN # FIXED
                    )

                if channel_message:
                    channel_msg_id = channel_message.id
                    fulfilled_link = channel_message.link # Get the permalink to the message in the channel
                    uploaded_successfully = True
                    logger.info(f"File for request {request_id} uploaded to channel {MOVIE_CHANNEL_ID} as message {channel_msg_id}.")
                else:
                    logger.error(f"Failed to get channel_message object after sending media for request {request_id}.")
                    await message.reply_text("Failed to post to channel. No message object returned.")

            elif message.text and (message.text.startswith("http://") or message.text.startswith("https://")):
                # Admin sent a URL
                fulfilled_link = message.text.strip()
                logger.info(f"Admin {user_id} sent a URL for request {request_id}: {fulfilled_link}.")

                # Post the URL to the channel with movie info
                channel_message = await client.send_message(
                    chat_id=MOVIE_CHANNEL_ID,
                    text=f"🎬 **{movie_title_for_channel}**\n\n"
                         f"🔗 **Direct Link:** [Click here]({fulfilled_link})\n\n"
                         f"📝 **Overview:** {movie_overview_for_channel}\n\n"
                         f"✨ Requested by user: [{request_data.get('user_name')}](tg://user?id={request_data.get('user_id')})"
                         f"\n\n#Movie #Request", # Example hashtags
                    parse_mode=ParseMode.MARKDOWN, # FIXED
                    disable_web_page_preview=False # Let Telegram show preview for URLs
                )
                if channel_message:
                    channel_msg_id = channel_message.id # Store the message ID of the text message with the link
                    uploaded_successfully = True
                    logger.info(f"URL for request {request_id} posted to channel {MOVIE_CHANNEL_ID} as message {channel_msg_id}.")
                else:
                    logger.error(f"Failed to get channel_message object after sending URL for request {request_id}.")
                    await message.reply_text("Failed to post URL to channel. No message object returned.")

            else:
                await message.reply_text("Please reply with a movie file (photo, video, document) or a direct URL.")
                return

            if uploaded_successfully:
                # Update request status and store the channel message ID and fulfilled link
                await update_request_status(request_id, "fulfilled", fulfilled_link)
                if channel_msg_id:
                    await update_movie_channel_id(request_id, channel_msg_id)

                await message.reply_text("Movie uploaded and indexed! User will be notified.")
                await clear_user_state(user_id) # Clear admin's state

                # Now, notify the original user
                user_id_to_notify = request_data["user_id"]
                tmdb_title = request_data["tmdb_title"]
                user_msg_id = request_data.get("original_user_request_msg_id")

                final_user_message_text = (
                    f"🎉 Great news! Your requested movie, **{tmdb_title}**, is now available!\n\n"
                    f"Click the button below to go directly to the movie in the channel.\n\n"
                    f"Enjoy your movie! 🍿"
                )

                # Ensure we have a valid link to the channel message
                # Prioritize the fulfilled_link if it's a direct URL, otherwise use the channel permalink
                go_to_movie_url = fulfilled_link if fulfilled_link and fulfilled_link.startswith("http") else f"https://t.me/{MOVIE_CHANNEL_ID.lstrip('@')}/{channel_msg_id}"

                reply_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("Go to Movie 🎬", url=go_to_movie_url)]
                ])

                # Try to edit the user's original request message
                if user_msg_id:
                    try:
                        await client.edit_message_text(
                            chat_id=user_id_to_notify,
                            message_id=user_msg_id,
                            text=final_user_message_text,
                            parse_mode=ParseMode.MARKDOWN, # FIXED
                            reply_markup=reply_keyboard
                        )
                    except Exception as e:
                        logger.warning(f"Could not edit original user message {user_msg_id} for user {user_id_to_notify}: {e}. Sending new message instead.")
                        await client.send_message(
                            chat_id=user_id_to_notify,
                            text=final_user_message_text,
                            parse_mode=ParseMode.MARKDOWN, # FIXED
                            reply_markup=reply_keyboard
                        )
                else: # If original message ID wasn't stored or is null
                    await client.send_message(
                        chat_id=user_id_to_notify,
                        text=final_user_message_text,
                        parse_mode=ParseMode.MARKDOWN, # FIXED
                        reply_markup=reply_keyboard
                    )

                # Update the admin's original approval message to reflect completion
                original_admin_message_id = request_data.get("admin_message_id")
                if original_admin_message_id:
                    try:
                        # Fetch the original caption before editing, to preserve it
                        original_admin_message = await client.get_messages(ADMIN_CHAT_ID, original_admin_message_id)
                        original_caption_content = original_admin_message.caption if original_admin_message.caption else ""

                        await client.edit_message_caption(
                            chat_id=ADMIN_CHAT_ID,
                            message_id=original_admin_message_id,
                            caption=original_caption_content +
                                    f"\n\n✅ **FULFILLED & INDEXED!**\n"
                                    f"Channel Message ID: `{channel_msg_id}`\n"
                                    f"Link: [Click Here]({go_to_movie_url})",
                            parse_mode=ParseMode.MARKDOWN, # FIXED
                            reply_markup=None # Remove all buttons
                        )
                    except Exception as e:
                        logger.warning(f"Could not edit original admin message {original_admin_message_id}: {e}")
                        await message.reply_text(f"Admin message update failed for request {request_id}. Please check the channel manually.")

            else:
                await message.reply_text("Failed to process your upload. Please try again.")

        except Exception as e:
            logger.error(f"Critical error handling admin upload for request {request_id}: {e}", exc_info=True)
            await message.reply_text(
                f"An unhandled error occurred during upload/indexing: {e}. Please check logs."
            )
            # Do NOT clear state on critical error, let admin manually clear or retry if possible
            # await clear_user_state(user_id)
    else:
        logger.debug(f"Admin {user_id} replied but not in 'awaiting_admin_upload' state. Ignoring or re-prompting.")
        # If the reply is not related to an awaited upload, you might want to:
        # 1. Simply ignore (pass)
        # 2. Send a generic "I'm not expecting an upload from you right now" message
        # 3. Check for other admin commands if any
        # For now, we'll just ignore if it's not a relevant state.
        pass
                
