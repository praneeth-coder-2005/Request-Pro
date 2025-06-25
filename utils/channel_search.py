import logging
from pyrogram import Client
from pyrogram.enums import ParseMode
import re

logger = logging.getLogger(__name__)

async def search_channel_messages(client: Client, channel_id: str, tmdb_id: int, tmdb_title: str) -> list:
    """
    Searches the channel history for messages related to a TMDB movie,
    prioritizing messages with a specific TMDB ID tag.

    Args:
        client: Pyrogram Client instance.
        channel_id: The username or ID of the channel to search.
        tmdb_id: The TMDB ID of the movie.
        tmdb_title: The title of the movie for keyword search.

    Returns:
        A list of dictionaries, each containing:
        - message_id: The ID of the message in the channel.
        - link: Permalink to the message.
        - caption: The message caption (cleaned if possible).
        - is_file: True if it's a media message (photo, video, document), False if text/link.
    """
    found_messages = []
    search_terms = []

    # 1. Prioritize searching by a specific TMDB ID tag
    # Encourage admins to tag uploads like: #TMDB<ID> (e.g., #TMDB857598)
    tmdb_tag = f"#TMDB{tmdb_id}"
    search_terms.append(tmdb_tag)

    # 2. Add cleaned movie title for broader search
    # Simple cleaning for search, consider more robust solutions if needed
    cleaned_title = re.sub(r'[^a-zA-Z0-9\s]', '', tmdb_title).strip()
    if cleaned_title:
        search_terms.append(cleaned_title)

    # Remove duplicates and ensure tags are first
    unique_search_terms = sorted(list(set(search_terms)), key=lambda x: (x.startswith("#TMDB"), x), reverse=True)

    logger.info(f"Searching channel '{channel_id}' for TMDB ID {tmdb_id} and terms: {unique_search_terms}")

    # Pyrogram's search_messages is limited, it searches visible history.
    # For a truly comprehensive search, a separate indexing process is needed.
    # Here we do a best-effort search.
    for term in unique_search_terms:
        try:
            # Iterate through search results
            async for message in client.search_messages(
                chat_id=channel_id,
                query=term,
                limit=50 # Limit search to recent 50 messages per term for performance
            ):
                # Check if the message is relevant (has media or a link)
                if message.media or (message.text and (message.text.startswith("http") or "link" in message.text.lower())):
                    # Basic check: does the TMDB ID appear in the caption/text if a tag was used?
                    # Or does the title roughly match?
                    is_relevant = False
                    caption_text = message.caption or message.text or ""
                    if tmdb_tag in caption_text:
                        is_relevant = True
                    elif re.search(r'\b' + re.escape(cleaned_title) + r'\b', caption_text, re.IGNORECASE):
                        is_relevant = True

                    if is_relevant:
                        # Avoid adding duplicates if multiple search terms find the same message
                        if not any(msg['message_id'] == message.id for msg in found_messages):
                            found_messages.append({
                                "message_id": message.id,
                                "link": message.link or f"https://t.me/{channel_id.lstrip('@')}/{message.id}",
                                "caption": caption_text,
                                "is_file": bool(message.media),
                                "date": message.date # Useful for sorting/prioritizing
                            })
        except Exception as e:
            logger.error(f"Error searching channel '{channel_id}' with term '{term}': {e}", exc_info=True)

    # Sort messages, e.g., by most recent or prioritize files
    found_messages.sort(key=lambda x: (x['is_file'], x['date']), reverse=True)

    return found_messages

