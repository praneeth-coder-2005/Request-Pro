# handlers/callbacks/admin_actions.py
import logging
from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.enums import ParseMode, ChatAction

from utils.database import get_request_by_id, update_request_status, clear_user_state, set_user_state
from utils.channel_search import search_channel_messages # Import for channel search
from config import ADMIN_CHAT_ID, MOVIE_CHANNEL_ID

logger = logging.getLogger(__name__)

async def handle_admin_approve_callback(client: Client, callback_query: CallbackQuery):
    """
    Handles admin approving a movie request.
    It now searches the movie channel and presents fulfillment options to the user.
    """
    request_id = int(callback_query.data.split("_")[2])
    request_data = await get_request_by_id(request_id)
    message = callback_query.message # The message the admin clicked on
    admin_id = callback_query.from_user.id

    if not request_data or request_data["status"] != "pending":
        await message.edit_caption(f"Request ID `{request_id}` is not pending or does not exist.")
        logger.warning(f"Admin tried to approve non-pending request {request_id}. Status: {request_data['status'] if request_data else 'None'}")
        return

    # Inform admin that search is in progress
    original_caption_parts = message.caption.split("\n\n")
    base_caption = original_caption_parts[0] # Keep the original request details

    await message.edit_caption(
        caption=f"{base_caption}\n\n"
                f"✅ **Approved by Admin.**\n\n"
                f"Searching channel `{str(MOVIE_CHANNEL_ID).lstrip('-100')}` for **{request_data['tmdb_title']}** (TMDB ID: `{request_data['tmdb_id']}`). This may take a moment...",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=None # Remove old buttons during search
    )
    await client.send_chat_action(message.chat.id, ChatAction.TYPING)

    # Search the movie channel
    found_messages = await search_channel_messages(
        client=client,
        channel_id=MOVIE_CHANNEL_ID,
        tmdb_id=request_data['tmdb_id'],
        tmdb_title=request_data['tmdb_title']
    )

    user_id_to_notify = request_data["user_id"]
    tmdb_title = request_data["tmdb_title"]
    # The user's message ID is retrieved from the database, not directly from state here,
    # as the 'awaiting_tmdb_selection' state has likely been cleared.
    user_original_message_id = request_data.get("original_user_request_msg_id")


    if not found_messages:
        # No movie found in channel
        await update_request_status(request_id, "approved_no_file_found") # New status to indicate it's approved but file missing

        admin_update_text = (
            f"{base_caption}\n\n"
            f"✅ **Approved by Admin.**\n\n"
            f"🚫 No relevant content found in channel `{str(MOVIE_CHANNEL_ID).lstrip('-100')}` for **{tmdb_title}** (TMDB ID: `{request_data['tmdb_id']}`).\n\n"
            "Please ensure the movie is uploaded to the channel with `#TMDB{ID}` in its caption."
        )
        await message.edit_caption(
            caption=admin_update_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Reject Request", callback_data=f"admin_reject_{request_id}")]
            ])
        )
        logger.warning(f"Admin approved request {request_id}, but no file found in channel {MOVIE_CHANNEL_ID}.")

        # Notify user that it's not available yet
        user_notification_text = (
            f"🙁 Your request for **{tmdb_title}** has been approved, "
            f"but the movie file is not yet available in the channel. "
            f"Please wait, or contact an administrator."
        )
        # Try to edit the user's *last* message in their private chat
        # If original_user_request_msg_id is not reliable, send a new message.
        try:
            # Attempt to edit the message where the user confirmed their request
            # This might be tricky if not stored correctly, so a new message is safer fallback
            await client.send_message(
                chat_id=user_id_to_notify,
                text=user_notification_text,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.warning(f"Failed to send/edit user notification for {user_id_to_notify}: {e}")
        return

    # Found messages: Prepare options for the user
    user_selection_buttons = []
    serializable_found_messages = [] # To store in user state

    for i, msg_info in enumerate(found_messages):
        # Try to extract a meaningful label from caption, otherwise fallback
        label = msg_info['caption'].split('\n')[0].strip() if msg_info['caption'] else f"Version {i+1} (Msg ID: {msg_info['message_id']})"
        # Also try to extract quality from caption if possible (e.g. [1080p])
        quality_match = re.search(r'\[(\d+p|HD|SD|4K)\]', msg_info['caption'], re.IGNORECASE)
        if quality_match:
            label = f"{tmdb_title} ({quality_match.group(1)})"
        elif len(label) > 60: # Truncate long labels
            label = label[:57] + "..."

        user_selection_buttons.append(
            [InlineKeyboardButton(label, callback_data=f"user_select_quality_{request_id}_{msg_info['message_id']}")]
        )
        serializable_found_messages.append({
            "message_id": msg_info['message_id'],
            "file_id": msg_info['file_id'], # file_id can be None for text_link
            "file_type": msg_info['file_type'],
            "link": msg_info['link'],
            "caption": msg_info['caption']
        })

    # Store found messages temporarily in user's state
    await set_user_state(
        user_id_to_notify,
        "awaiting_movie_quality_selection",
        {"request_id": request_id, "found_channel_options": serializable_found_messages}
    )
    logger.info(f"Admin {admin_id} approved request {request_id}. User {user_id_to_notify} now awaiting quality selection.")

    # Update admin message
    await message.edit_caption(
        caption=f"{base_caption}\n\n"
                f"✅ **Approved by Admin.**\n"
                f"Options sent to user **{request_data['user_name']}** for **{tmdb_title}**.\n"
                f"Waiting for user to select a quality.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Reject Request", callback_data=f"admin_reject_{request_id}")] # Keep reject option
        ])
    )
    logger.info(f"Admin message for request {request_id} updated after sending options to user.")

    # Notify the user with options
    user_notification_text = (
        f"🎉 Great news! Your requested movie, **{tmdb_title}**, is now available in multiple versions!\n\n"
        f"Please select your preferred quality below:"
    )

    try:
        # Send a *new* message to the user with the quality selection,
        # as their previous messages might be from a different state/context
        await client.send_message(
            chat_id=user_id_to_notify,
            text=user_notification_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(user_selection_buttons)
        )
        logger.info(f"New message sent to user {user_id_to_notify} with quality options for request {request_id}.")
    except Exception as e:
        logger.warning(f"Failed to send quality options to user {user_id_to_notify}: {e}")


async def handle_admin_reject_callback(client: Client, callback_query: CallbackQuery):
    """Handles admin rejecting a movie request."""
    request_id = int(callback_query.data.split("_")[2])
    request_data = await get_request_by_id(request_id)
    message = callback_query.message
    admin_id = callback_query.from_user.id

    if not request_data or request_data["status"] not in ["pending", "approved", "approved_no_file_found"]:
        await message.edit_caption(f"Request ID `{request_id}` is not active or does not exist.")
        logger.warning(f"Admin tried to reject non-active request {request_id}. Status: {request_data['status'] if request_data else 'None'}")
        return

    await update_request_status(request_id, "rejected")
    await message.edit_reply_markup(reply_markup=None)

    # Preserve original caption content but add rejection status
    original_caption_parts = message.caption.split("\n\n")
    base_caption = original_caption_parts[0]

    await message.edit_caption(
        caption=f"{base_caption}\n\n❌ **Request Rejected by Admin.**",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        # Clear user's state if they were awaiting selection (important!)
        await clear_user_state(request_data["user_id"])
        await client.send_message(
            chat_id=request_data["user_id"],
            text=f"🙁 We're sorry, your request for **{request_data['tmdb_title']}** could not be fulfilled at this time. "
                "Please try again later or request a different movie.",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.warning(f"Failed to notify user {request_data['user_id']} about rejected request {request_id}: {e}")

    logger.info(f"Admin rejected request {request_id}.")

