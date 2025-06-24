# handlers/callbacks/admin_actions.py
import logging
from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.enums import ParseMode, ChatAction # Added ChatAction

from utils.database import get_request_by_id, update_request_status, set_user_state, clear_user_state, update_movie_channel_id
from utils.channel_search import search_channel_messages # NEW IMPORT for channel search
from config import ADMIN_CHAT_ID, MOVIE_CHANNEL_ID # Only ADMIN_CHAT_ID needed here

logger = logging.getLogger(__name__)

async def handle_admin_approve_callback(client: Client, callback_query: CallbackQuery):
    """
    Handles admin approving a movie request.
    Now presents options for fulfillment (search channel or manual link).
    """
    request_id = int(callback_query.data.split("_")[2])
    request_data = await get_request_by_id(request_id)
    message = callback_query.message # The message the admin clicked on

    if not request_data or request_data["status"] != "pending":
        await message.edit_text(f"Request ID `{request_id}` is not pending or does not exist.")
        logger.warning(f"Admin tried to approve non-pending request {request_id}. Status: {request_data['status'] if request_data else 'None'}")
        return

    # Update request status to 'approved' but not yet fulfilled
    await update_request_status(request_id, "approved")

    # Set admin's state to awaiting decision for fulfillment method
    await set_user_state(
        callback_query.from_user.id,
        "awaiting_fulfillment_method",
        {"request_id": request_id}
    )
    logger.info(f"Admin {callback_query.from_user.id} set to 'awaiting_fulfillment_method' for request {request_id}.")

    # Change admin message buttons and text to prompt for fulfillment method
    fulfillment_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Search & Index in Channel", callback_data=f"admin_search_channel_{request_id}")],
        [InlineKeyboardButton("🔗 Manually Input Link", callback_data=f"admin_manual_link_{request_id}")],
        [InlineKeyboardButton("❌ Reject Request", callback_data=f"admin_reject_{request_id}")] # Keep reject option
    ])

    await message.edit_reply_markup(reply_markup=fulfillment_keyboard)
    await message.edit_caption(
        caption=message.caption.split("\n\n✅ **Approved by Admin.**")[0] + # Keep original request text
                "\n\n✅ **Approved by Admin.**\n\n"
                "How would you like to fulfill this request?\n"
                "- **Search & Index**: I will search the movie channel for existing files/links.\n"
                "- **Manually Input Link**: You provide a direct download link, and I will post it.",
        parse_mode=ParseMode.MARKDOWN
    )
    logger.info(f"Admin approved request {request_id}. Prompted for fulfillment method.")


async def handle_admin_search_channel_callback(client: Client, callback_query: CallbackQuery):
    """
    Handles admin choosing to search the movie channel for the requested movie.
    """
    request_id = int(callback_query.data.split("_")[3]) # admin_search_channel_<request_id>
    request_data = await get_request_by_id(request_id)
    message = callback_query.message
    admin_id = callback_query.from_user.id

    if not request_data or request_data["status"] != "approved":
        await message.edit_text(f"Request ID `{request_id}` is not approved or does not exist. Current status: {request_data['status'] if request_data else 'None'}")
        logger.warning(f"Admin tried to search channel for non-approved request {request_id}.")
        return

    await message.edit_text(f"Searching channel `{MOVIE_CHANNEL_ID}` for **{request_data['tmdb_title']}** (TMDB ID: `{request_data['tmdb_id']}`). This may take a moment...")
    await client.send_chat_action(message.chat.id, ChatAction.TYPING)

    found_messages = await search_channel_messages(
        client=client,
        channel_id=MOVIE_CHANNEL_ID,
        tmdb_id=request_data['tmdb_id'],
        tmdb_title=request_data['tmdb_title']
    )

    if not found_messages:
        await message.edit_text(
            f"No relevant content found in channel `{MOVIE_CHANNEL_ID}` for **{request_data['tmdb_title']}** (TMDB ID: `{request_data['tmdb_id']}`).\n\n"
            "Please ensure the movie is uploaded to the channel, preferably with `#TMDB{ID}` in its caption.\n\n"
            "You can still choose to **Manually Input Link**."
        )
        # Re-offer options if nothing found
        fulfillment_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Manually Input Link", callback_data=f"admin_manual_link_{request_id}")],
            [InlineKeyboardButton("❌ Reject Request", callback_data=f"admin_reject_{request_id}")]
        ])
        await message.edit_reply_markup(reply_markup=fulfillment_keyboard)
        await clear_user_state(admin_id) # Clear admin state if nothing found, allow re-trigger
        return

    # Store found messages in admin's state for later selection
    # We need to map actual message objects to something serializable
    serializable_messages = [
        {
            "message_id": msg["message_id"],
            "link": msg["link"],
            "caption": msg["caption"]
        } for msg in found_messages
    ]
    await set_user_state(
        admin_id,
        "awaiting_channel_selection",
        {"request_id": request_id, "found_channel_messages": serializable_messages}
    )
    logger.info(f"Admin {admin_id} found {len(found_messages)} messages for request {request_id}. Presenting options.")

    # Present found messages as inline buttons
    selection_buttons = []
    for i, msg in enumerate(found_messages):
        # Try to extract a meaningful label from caption or just use a generic one
        label = msg['caption'].split('\n')[0].strip() if msg['caption'] else f"Message {msg['message_id']}"
        if len(label) > 60: # Truncate long labels
            label = label[:57] + "..."
        selection_buttons.append(
            [InlineKeyboardButton(label, callback_data=f"admin_select_channel_msg_{request_id}_{msg['message_id']}")]
        )

    selection_buttons.append([InlineKeyboardButton("None of these, or Manual Link", callback_data=f"admin_manual_link_{request_id}")])

    await message.edit_text(
        f"Found these potential matches for **{request_data['tmdb_title']}** in `{MOVIE_CHANNEL_ID}`. "
        "Please select the correct one to fulfill the request:\n\n" +
        "\n".join([f"- [{msg['caption'].splitlines()[0][:50] + '...' if msg['caption'] else 'Message '+str(msg['message_id'])}]({msg['link']})" for msg in found_messages[:5]]), # Show links for reference
        reply_markup=InlineKeyboardMarkup(selection_buttons),
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )

async def handle_admin_select_channel_msg_callback(client: Client, callback_query: CallbackQuery):
    """
    Handles admin selecting a specific message from the channel to fulfill the request.
    """
    parts = callback_query.data.split("_")
    request_id = int(parts[3])
    selected_channel_msg_id = int(parts[4])
    message = callback_query.message
    admin_id = callback_query.from_user.id

    state, state_data = await get_user_state(admin_id)

    if state != "awaiting_channel_selection" or not state_data or state_data["request_id"] != request_id:
        await message.edit_text("This selection is no longer valid or incomplete. Please start over from admin approval.")
        await clear_user_state(admin_id)
        return

    request_data = await get_request_by_id(request_id)
    if not request_data or request_data["status"] not in ["approved", "pending"]: # Allow "pending" in case state was cleared prematurely
        await message.edit_text(f"Request ID `{request_id}` is not active or does not exist.")
        await clear_user_state(admin_id)
        return

    # Find the selected message details from state_data
    selected_message_details = next((msg for msg in state_data["found_channel_messages"] if msg["message_id"] == selected_channel_msg_id), None)

    if not selected_message_details:
        await message.edit_text("Selected channel message details not found in session data. Please try re-searching or provide a manual link.")
        return

    await message.edit_text("Finalizing fulfillment...")
    await client.send_chat_action(message.chat.id, ChatAction.TYPING)

    fulfilled_link = selected_message_details.get("link") or f"https://t.me/{MOVIE_CHANNEL_ID.lstrip('@')}/{selected_channel_msg_id}"

    # Update request status and store the channel message ID and fulfilled link
    await update_request_status(request_id, "fulfilled", fulfilled_link)
    await update_movie_channel_id(request_id, selected_channel_msg_id)
    await clear_user_state(admin_id) # Clear admin's state

    await message.edit_reply_markup(reply_markup=None) # Remove buttons

    # Now, notify the original user and update admin message
    await notify_user_and_update_admin_message(
        client,
        request_data,
        channel_msg_id=selected_channel_msg_id,
        fulfilled_link=fulfilled_link
    )
    logger.info(f"Request {request_id} fulfilled by admin {admin_id} using channel message {selected_channel_msg_id}.")


async def handle_admin_manual_link_callback(client: Client, callback_query: CallbackQuery):
    """
    Handles admin choosing to manually input a direct download link.
    """
    request_id = int(callback_query.data.split("_")[3]) # admin_manual_link_<request_id>
    request_data = await get_request_by_id(request_id)
    message = callback_query.message
    admin_id = callback_query.from_user.id

    if not request_data or request_data["status"] not in ["approved", "pending"]: # Allow "pending" if state was cleared
        await message.edit_text(f"Request ID `{request_id}` is not active or does not exist.")
        return

    await set_user_state(
        admin_id,
        "awaiting_manual_link",
        {"request_id": request_id}
    )
    logger.info(f"Admin {admin_id} set to 'awaiting_manual_link' for request {request_id}.")

    await message.edit_reply_markup(reply_markup=None) # Remove old buttons
    await message.edit_text(
        f"Please **REPLY to this message** with the direct download link for **{request_data['tmdb_title']}**.\n\n"
        "This link will be posted to the movie channel and sent to the user.",
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_admin_reject_callback(client: Client, callback_query: CallbackQuery):
    """Handles admin rejecting a movie request."""
    request_id = int(callback_query.data.split("_")[2])
    request_data = await get_request_by_id(request_id)
    message = callback_query.message
    admin_id = callback_query.from_user.id

    if not request_data or request_data["status"] not in ["pending", "approved", "awaiting_fulfillment_method", "awaiting_channel_selection", "awaiting_manual_link"]:
        await message.edit_text(f"Request ID `{request_id}` is not active or does not exist.")
        logger.warning(f"Admin tried to reject non-active request {request_id}. Status: {request_data['status'] if request_data else 'None'}")
        return

    await update_request_status(request_id, "rejected")
    await message.edit_reply_markup(reply_markup=None)
    await message.edit_caption(
        caption=message.caption.split("\n\n✅ **Approved by Admin.**")[0] + "\n\n❌ **Request Rejected by Admin.**",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        await client.send_message(
            chat_id=request_data["user_id"],
            text=f"🙁 We're sorry, your request for **{request_data['tmdb_title']}** could not be fulfilled at this time. "
                "Please try again later or request a different movie.",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.warning(f"Failed to notify user {request_data['user_id']} about rejected request {request_id}: {e}")

    await clear_user_state(admin_id) # Clear admin's state as this is a terminal action
    logger.info(f"Admin rejected request {request_id}.")


async def notify_user_and_update_admin_message(client: Client, request_data: dict, channel_msg_id: int = None, fulfilled_link: str = None):
    """
    Helper function to notify the user and update the admin's original message
    after a request has been fulfilled.
    """
    user_id_to_notify = request_data["user_id"]
    tmdb_title = request_data["tmdb_title"]
    user_msg_id = request_data.get("original_user_request_msg_id")
    request_id = request_data["id"] # Get the request ID

    final_user_message_text = (
        f"🎉 Great news! Your requested movie, **{tmdb_title}**, is now available!\n\n"
        f"Click the button below to go directly to the movie in the channel.\n\n"
        f"Enjoy your movie! 🍿"
    )

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
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_keyboard
            )
            logger.info(f"User {user_id_to_notify}'s original message {user_msg_id} edited for request {request_id}.")
        except Exception as e:
            logger.warning(f"Could not edit original user message {user_msg_id} for user {user_id_to_notify}: {e}. Sending new message instead.")
            await client.send_message(
                chat_id=user_id_to_notify,
                text=final_user_message_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_keyboard
            )
    else: # If original message ID wasn't stored or is null
        await client.send_message(
            chat_id=user_id_to_notify,
            text=final_user_message_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_keyboard
        )
        logger.info(f"New message sent to user {user_id_to_notify} for request {request_id}.")

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
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=None # Remove all buttons
            )
            logger.info(f"Admin message {original_admin_message_id} updated for request {request_id}.")
        except Exception as e:
            logger.warning(f"Could not edit original admin message {original_admin_message_id}: {e}")
            # Optionally send a new message to admin if edit fails
            await client.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"Fulfillment notification for request `{request_id}` sent to user. "
                     f"However, I couldn't update the original admin message {original_admin_message_id}. "
                     f"Movie Link: {go_to_movie_url}",
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
    )
    
