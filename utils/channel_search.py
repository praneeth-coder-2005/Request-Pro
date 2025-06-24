import logging
from pyrogram import Client
import re

logger = logging.getLogger(__name__)

async def search_channel_messages(client: Client, channel_id: int, tmdb_id: int, tmdb_title: str) -> list:
    """
    Searches the specified channel history for messages related to a TMDB movie,
    prioritizing messages with a specific TMDB ID tag.

    Args:
        client: Pyrogram Client instance.
        channel_id: The NUMERIC ID of the channel to search.
        tmdb_id: The TMDB ID of the movie.
        tmdb_title: The title of the movie for keyword search (fallback).

    Returns:
        A list of dictionaries, each containing:
        - message_id: The ID of the message in the channel.
        - link: Permalink to the message.
        - caption: The message caption (cleaned if possible).
        - is_media: True if it's a media message (photo, video, document), False if text/link.
        - file_id: The file_id of the media, if present.
        - file_type: The type of media (e.g., 'video', 'document', 'photo').
    """
    found_messages = []
    search_terms = []

    # 1. Prioritize searching by a specific TMDB ID tag
    tmdb_tag = f"#TMDB{tmdb_id}"
    search_terms.append(tmdb_tag)

    # 2. Add cleaned movie title for broader search (as fallback if tag isn't used consistently)
    cleaned_title = re.sub(r'[^a-zA-Z0-9\s]', '', tmdb_title).strip()
    if cleaned_title and cleaned_title.lower() != "none": # Avoid searching "None"
        search_terms.append(cleaned_title)

    # Use a set to avoid duplicate searches, and sort to prioritize TMDB tag
    unique_search_terms = sorted(list(set(search_terms)), key=lambda x: (x.startswith("#TMDB"), x), reverse=True)

    logger.info(f"Searching channel '{channel_id}' for TMDB ID {tmdb_id} and terms: {unique_search_terms}")

    for term in unique_search_terms:
        try:
            # Iterate through search results - Pyrogram's search_messages is efficient for recent history
            # Limit can be adjusted, but a higher limit means more API calls and potential rate limits
            async for message in client.search_messages(
                chat_id=channel_id,
                query=term,
                limit=50 # Adjusted limit, can increase if needed
            ):
                # Check if the message is relevant (has media or a direct link in text)
                is_media = False
                file_id = None
                file_type = None

                if message.video:
                    is_media = True
                    file_id = message.video.file_id
                    file_type = 'video'
                elif message.document:
                    is_media = True
                    file_id = message.document.file_id
                    file_type = 'document'
                elif message.photo: # Could be a movie poster, less likely to be the movie itself
                    is_media = True
                    file_id = message.photo.file_id
                    file_type = 'photo'
                elif message.text and (message.text.startswith("http") or "link" in message.text.lower()):
                    # It's a text message that looks like a link post
                    is_media = False # Treat as not "media" for sending purposes, but still relevant
                    file_id = None # No file_id for direct text links
                    file_type = 'text_link'

                if is_media or file_type == 'text_link': # Only consider messages with media or direct links
                    caption_text = message.caption or message.text or ""

                    # Refine relevance check: must contain the TMDB tag OR a strong title match
                    is_relevant = False
                    if tmdb_tag in caption_text:
                        is_relevant = True
                    elif cleaned_title and re.search(r'\b' + re.escape(cleaned_title) + r'\b', caption_text, re.IGNORECASE):
                        is_relevant = True

                    if is_relevant:
                        # Avoid adding duplicates if multiple search terms find the same message
                        if not any(msg['message_id'] == message.id for msg in found_messages):
                            found_messages.append({
                                "message_id": message.id,
                                "link": message.link or f"https://t.me/{str(channel_id).lstrip('-100')}/{message.id}", # Fallback for link
                                "caption": caption_text,
                                "is_media": is_media,
                                "file_id": file_id,
                                "file_type": file_type,
                                "date": message.date # For sorting by recency
                            })
        except Exception as e:
            logger.error(f"Error searching channel '{channel_id}' with term '{term}': {e}", exc_info=True)

    # Sort messages: prioritize by files first (more reliable), then by most recent
    found_messages.sort(key=lambda x: (x['is_media'], x['date']), reverse=True)

    return found_messages

                                   
