# handlers/callbacks/admin_actions.py
import logging
from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.enums import ParseMode

from utils.database import get_request_by_id, update_request_status, clear_user_state
from config import ADMIN_CHAT_ID, MOVIE_CHANNEL_ID # MOVIE_CHANNEL_ID is used for instruction text

logger = logging.getLogger(__name__)

async def handle_admin_approve_callback(client: Client, callback_query: CallbackQuery):
    """
    Handles admin approving a movie request.
    Now simply changes status to 'approved' and instructs admin to upload to channel
    with a #TMDB<ID> tag for auto-indexing.
    """
    request_id = int(callback_query.data.split("_")[2])
    request_data = await get_request_by_id(request_id)
    message = callback_query.message # The message the admin clicked on
    admin_id = callback_query.from_user.id

    if not request_data or request_data["status"] != "pending":
        await message.edit_text(f"Request ID `{request_id}` is not pending or does not exist.")
        logger.warning(f"Admin tried to approve non-pending request {request_id}. Status: {request_data['status'] if request_data else 'None'}")
        return

    # Update request status to 'approved'
    await update_request_status(request_id, "approved")
    logger.info(f"Admin {admin_id} approved request {request_id}. Status set to 'approved'.")

    # Remove the old buttons
    await message.edit_reply_markup(reply_markup=None)

    # Prepare channel username or ID string for instructions
    channel_info_for_caption = str(MOVIE_CHANNEL_ID)
    try:
        chat_obj = await client.get_chat(MOVIE_CHANNEL_ID)
        if chat_obj and chat_obj.username:
            channel_info_for_caption = f"@{chat_obj.username}"
        elif chat_obj: # If no username, use title
            channel_info_for_caption = f"'{chat_obj.title}' (ID: `{MOVIE_CHANNEL_ID}`)"
    except Exception as e:
        logger.warning(f"Could not get channel info for {MOVIE_CHANNEL_ID}: {e}. Using raw ID for instruction.")


    # Inform the admin about the next steps for auto-indexing
    original_caption_content = message.caption if message.caption else ""
    await message.edit_caption(
        caption=original_caption_content.split("\n\n✅ **Approved by Admin.**")[0] + # Ensure original text is kept if already edited once
                f"\n\n✅ **Approved by Admin.**\n\n"
                f"To fulfill this request, please upload the movie directly to the channel "
                f"`{channel_info_for_caption}`.\n\n"
                f"**IMPORTANT:** Include `#TMDB{request_data['tmdb_id']}` in the caption of your post. "
                "The bot will automatically detect it, mark the request as fulfilled, and notify the user.\n\n"
                "You can still reject this request if you change your mind.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Reject This Request", callback_data=f"admin_reject_{request_id}")]
        ])
    )
    logger.info(f"Admin {admin_id} received instructions for fulfilling request {request_id}.")

async def handle_admin_reject_callback(client: Client, callback_query: CallbackQuery):
    """Handles admin rejecting a movie request."""
    request_id = int(callback_query.data.split("_")[2])
    request_data = await get_request_by_id(request_id)
    message = callback_query.message
    admin_id = callback_query.from_user.id

    if not request_data or request_data["status"] not in ["pending", "approved"]:
        await message.edit_text(f"Request ID `{request_id}` is not active or does not exist.")
        logger.warning(f"Admin tried to reject non-active request {request_id}. Status: {request_data['status'] if request_data else 'None'}")
        return

    await update_request_status(request_id, "rejected")
    await message.edit_reply_markup(reply_markup=None)
    # Ensure caption trimming if it became too long
    original_caption_content = message.caption.split("\n\n✅ **Approved by Admin.**")[0] if "\n\n✅ **Approved by Admin.**" in message.caption else message.caption
    await message.edit_caption(
        caption=original_caption_content + "\n\n❌ **Request Rejected by Admin.**",
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

    # It's good practice to clear any lingering admin state, though less critical with this new flow
    await clear_user_state(admin_id)
    logger.info(f"Admin rejected request {request_id}.")

