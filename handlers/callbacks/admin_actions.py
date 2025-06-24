# handlers/callbacks/admin_actions.py
import logging
from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.enums import ParseMode # ADDED ParseMode here
from utils.database import get_request_by_id, update_request_status, set_user_state, clear_user_state
from config import ADMIN_CHAT_ID # Only ADMIN_CHAT_ID needed here

logger = logging.getLogger(__name__)

async def handle_admin_approve_callback(client: Client, callback_query: CallbackQuery):
    """Handles admin approving a movie request."""
    request_id = int(callback_query.data.split("_")[2])
    request_data = await get_request_by_id(request_id)
    message = callback_query.message # The message the admin clicked on

    if not request_data or request_data["status"] != "pending":
        await message.edit_text(f"Request ID `{request_id}` is not pending or does not exist.")
        logger.warning(f"Admin tried to approve non-pending request {request_id}. Status: {request_data['status'] if request_data else 'None'}")
        return

    await update_request_status(request_id, "approved_by_admin")

    # Set admin's state to awaiting file/link for this specific request
    await set_user_state(
        callback_query.from_user.id,
        "awaiting_admin_upload",
        {"request_id": request_id}
    )
    logger.info(f"Admin {callback_query.from_user.id} set to 'awaiting_admin_upload' for request {request_id}.")

    # Change admin message buttons and text to prompt for upload
    await message.edit_reply_markup(reply_markup=None) # Remove old buttons first
    await message.edit_caption(
        caption=message.caption + "\n\n✅ **Approved by Admin.**\n\n"
                "**Please REPLY to this message with the movie file(s) or a direct download link.** "
                "I will upload it to the channel and index it automatically.",
        parse_mode=ParseMode.MARKDOWN # FIXED
    )
    logger.info(f"Admin approved request {request_id}. Prompted for file/URL upload.")

async def handle_admin_reject_callback(client: Client, callback_query: CallbackQuery):
    """Handles admin rejecting a movie request."""
    request_id = int(callback_query.data.split("_")[2])
    request_data = await get_request_by_id(request_id)
    message = callback_query.message

    if not request_data or request_data["status"] != "pending":
        await message.edit_text(f"Request ID `{request_id}` is not pending or does not exist.")
        logger.warning(f"Admin tried to reject non-pending request {request_id}. Status: {request_data['status'] if request_data else 'None'}")
        return

    await update_request_status(request_id, "rejected")
    await message.edit_reply_markup(reply_markup=None)
    await message.edit_caption(
        caption=message.caption + "\n\n❌ **Request Rejected by Admin.**",
        parse_mode=ParseMode.MARKDOWN # FIXED
    )
    try:
        await client.send_message(
            chat_id=request_data["user_id"],
            text=f"🙁 We're sorry, your request for **{request_data['tmdb_title']}** could not be fulfilled at this time. "
                 "Please try again later or request a different movie.",
            parse_mode=ParseMode.MARKDOWN # FIXED
        )
    except Exception as e:
        logger.warning(f"Failed to notify user {request_data['user_id']} about rejected request {request_id}: {e}")
    logger.info(f"Admin rejected request {request_id}.")

async def handle_admin_complete_fulfillment_callback(client: Client, callback_query: CallbackQuery):
    """
    Placeholder: This callback is likely deprecated in the new flow
    where admin simply replies with the file/URL.
    """
    await callback_query.answer("This button's functionality has been integrated into the file/URL reply mechanism.")
    logger.info(f"Admin {callback_query.from_user.id} clicked deprecated fulfillment button.")
    
