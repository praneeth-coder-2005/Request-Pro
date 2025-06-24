# handlers/callback_handler.py
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery
import logging

# Import handler functions from our sub-modules
from .callbacks.user_requests import handle_select_tmdb_callback, handle_none_correct_callback, handle_confirm_request_callback
from .callbacks.admin_actions import (
    handle_admin_approve_callback,
    handle_admin_reject_callback,
)
from .callbacks.user_fulfillment_actions import handle_user_select_quality_callback # NEW import

logger = logging.getLogger(__name__)

@Client.on_callback_query()
async def handle_callback_query(client: Client, callback_query: CallbackQuery):
    """
    Central callback query handler that dispatches to specific handlers
    based on the callback_data prefix.
    """
    data = callback_query.data
    user_id = callback_query.from_user.id

    logger.info(f"CallbackQuery received: {data} from user {user_id}")

    # Acknowledge the callback immediately to remove the loading animation
    await callback_query.answer()

    if data.startswith("select_tmdb_"):
        await handle_select_tmdb_callback(client, callback_query)
    elif data == "tmdb_none_correct":
        await handle_none_correct_callback(client, callback_query)
    elif data.startswith("confirm_request_"):
        await handle_confirm_request_callback(client, callback_query)
    elif data.startswith("admin_approve_"):
        await handle_admin_approve_callback(client, callback_query)
    elif data.startswith("admin_reject_"):
        await handle_admin_reject_callback(client, callback_query)
    elif data.startswith("user_select_quality_"): # NEW route for user selecting quality
        await handle_user_select_quality_callback(client, callback_query)
    else:
        logger.warning(f"Unknown callback data received: {data} from user {user_id}")
        await callback_query.message.edit_text("Unknown action. Please try again or start over.")

