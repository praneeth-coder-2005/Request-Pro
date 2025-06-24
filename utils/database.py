
import aiosqlite
import logging
import json
import time
from config import DATABASE_URL, STATE_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

# Extract path from DATABASE_URL for aiosqlite
DB_FILE = DATABASE_URL.replace("sqlite:///", "")

async def init_db():
    """Initializes the SQLite database and creates tables if they don't exist."""
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS movie_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                user_name TEXT,
                tmdb_id INTEGER,
                tmdb_title TEXT,
                tmdb_poster_path TEXT,
                status TEXT NOT NULL DEFAULT 'pending', -- pending, approved, approved_no_file_found, fulfilled, rejected
                request_timestamp INTEGER NOT NULL,
                fulfilled_timestamp INTEGER,
                fulfilled_link TEXT,
                channel_message_id INTEGER, -- New: to store the ID of the message in the movie channel
                admin_message_id INTEGER -- New: to store the ID of the admin's forwarded message
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_states (
                user_id INTEGER PRIMARY KEY,
                state TEXT NOT NULL,
                data TEXT,
                timestamp INTEGER NOT NULL
            )
        """)
        await db.commit()
    logger.info(f"Database {DB_FILE} initialized successfully.")

async def add_movie_request(user_id: int, user_name: str, tmdb_id: int, tmdb_title: str, tmdb_poster_path: str = None, admin_message_id: int = None):
    """Adds a new movie request to the database."""
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            "INSERT INTO movie_requests (user_id, user_name, tmdb_id, tmdb_title, tmdb_poster_path, request_timestamp, admin_message_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, user_name, tmdb_id, tmdb_title, tmdb_poster_path, int(time.time()), admin_message_id)
        )
        await db.commit()
        return cursor.lastrowid

async def get_request_by_id(request_id: int):
    """Retrieves a movie request by its ID."""
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM movie_requests WHERE id = ?", (request_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def update_request_status(request_id: int, status: str, fulfilled_link: str = None):
    """Updates the status of a movie request."""
    async with aiosqlite.connect(DB_FILE) as db:
        current_time = int(time.time()) if status == "fulfilled" else None
        await db.execute(
            "UPDATE movie_requests SET status = ?, fulfilled_timestamp = ?, fulfilled_link = ? WHERE id = ?",
            (status, current_time, fulfilled_link, request_id)
        )
        await db.commit()
        logger.info(f"Request {request_id} status updated to {status}.")

async def update_movie_channel_id(request_id: int, channel_message_id: int):
    """Updates the channel_message_id for a fulfilled request."""
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "UPDATE movie_requests SET channel_message_id = ? WHERE id = ?",
            (channel_message_id, request_id)
        )
        await db.commit()
        logger.info(f"Request {request_id} channel_message_id updated to {channel_message_id}.")


async def set_user_state(user_id: int, state: str, data: dict = None):
    """Sets or updates the state and associated data for a user."""
    async with aiosqlite.connect(DB_FILE) as db:
        json_data = json.dumps(data) if data else None
        current_time = int(time.time())
        await db.execute(
            "INSERT OR REPLACE INTO user_states (user_id, state, data, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, state, json_data, current_time)
        )
        await db.commit()
        logger.debug(f"User {user_id} state set to '{state}' with data: {data}")

async def get_user_state(user_id: int):
    """Retrieves the current state and data for a user, clearing if expired."""
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM user_states WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if row:
            if int(time.time()) - row['timestamp'] > STATE_TIMEOUT_SECONDS:
                await clear_user_state(user_id)
                logger.debug(f"User {user_id} state expired and cleared.")
                return None, None # State expired
            return row['state'], json.loads(row['data']) if row['data'] else {}
        return None, None

async def clear_user_state(user_id: int):
    """Clears the state for a specific user."""
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM user_states WHERE user_id = ?", (user_id,))
        await db.commit()
        logger.debug(f"User {user_id} state cleared.")

