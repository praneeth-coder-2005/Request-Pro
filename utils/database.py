# utils/database.py (extended)
import aiosqlite
import asyncio
from datetime import datetime

DATABASE_NAME = "movie_bot.db" # Renamed for clarity

async def init_db():
    """Initializes the database connection and creates tables."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        # Table for permanent movie requests
        await db.execute("""
            CREATE TABLE IF NOT EXISTS movie_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                user_name TEXT,
                tmdb_id INTEGER,
                tmdb_title TEXT NOT NULL,
                tmdb_overview TEXT,
                tmdb_poster_path TEXT,
                request_time TEXT NOT NULL,
                status TEXT NOT NULL, -- 'pending', 'fulfilled', 'rejected', 'temp_selected'
                fulfilled_link TEXT,
                admin_message_id INTEGER,
                original_user_request_msg_id INTEGER -- To know which message to edit for user
            )
        """)
        # Table for temporary user states during the request process
        # This helps manage multi-step interactions like TMDB search result selection
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_states (
                user_id INTEGER PRIMARY KEY,
                state TEXT NOT NULL, -- e.g., 'awaiting_tmdb_selection'
                data TEXT -- JSON string of relevant data, e.g., list of TMDB results
            )
        """)
        await db.commit()
    print("Database initialized (movie_requests & user_states tables).")


# --- Movie Request Functions ---

async def add_movie_request(request_data: dict) -> int:
    """Adds a new movie request to the database."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute(
            """
            INSERT INTO movie_requests
            (user_id, user_name, tmdb_id, tmdb_title, tmdb_overview, tmdb_poster_path, request_time, status, original_user_request_msg_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_data["user_id"],
                request_data["user_name"],
                request_data.get("tmdb_id"),
                request_data["tmdb_title"],
                request_data.get("tmdb_overview"),
                request_data.get("tmdb_poster_path"),
                datetime.now().isoformat(),
                request_data.get("status", "pending"),
                request_data.get("original_user_request_msg_id")
            )
        )
        await db.commit()
        return cursor.lastrowid

async def get_request_by_id(request_id: int) -> dict | None:
    """Retrieves a movie request by its ID."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM movie_requests WHERE id = ?",
            (request_id,)
        )
        row = await cursor.fetchone()
        if row:
            data = dict(row)
            if data.get("request_time"):
                data["request_time"] = datetime.fromisoformat(data["request_time"])
            return data
        return None

async def update_request_status(request_id: int, status: str, fulfilled_link: str = None) -> bool:
    """Updates the status of a movie request."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        if fulfilled_link:
            cursor = await db.execute(
                "UPDATE movie_requests SET status = ?, fulfilled_link = ? WHERE id = ?",
                (status, fulfilled_link, request_id)
            )
        else:
            cursor = await db.execute(
                "UPDATE movie_requests SET status = ? WHERE id = ?",
                (status, request_id)
            )
        await db.commit()
        return cursor.rowcount > 0

async def update_request_admin_message_id(request_id: int, admin_message_id: int) -> bool:
    """Updates the admin message ID for a request."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute(
            "UPDATE movie_requests SET admin_message_id = ? WHERE id = ?",
            (admin_message_id, request_id)
        )
        await db.commit()
        return cursor.rowcount > 0

async def get_user_requests(user_id: int) -> list[dict]:
    """Retrieves all active requests for a specific user."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM movie_requests WHERE user_id = ? AND status IN ('pending', 'temp_selected') ORDER BY request_time DESC",
            (user_id,)
        )
        rows = await cursor.fetchall()
        requests = []
        for row in rows:
            data = dict(row)
            if data.get("request_time"):
                data["request_time"] = datetime.fromisoformat(data["request_time"])
            requests.append(data)
        return requests

# --- User State Functions ---
import json

async def set_user_state(user_id: int, state: str, data: dict = None):
    """Sets a user's current interaction state."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        data_str = json.dumps(data) if data else None
        await db.execute(
            """
            INSERT OR REPLACE INTO user_states (user_id, state, data)
            VALUES (?, ?, ?)
            """,
            (user_id, state, data_str)
        )
        await db.commit()

async def get_user_state(user_id: int) -> tuple[str | None, dict | None]:
    """Gets a user's current interaction state and associated data."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT state, data FROM user_states WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if row:
            state = row["state"]
            data = json.loads(row["data"]) if row["data"] else None
            return state, data
        return None, None

async def clear_user_state(user_id: int):
    """Clears a user's interaction state."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("DELETE FROM user_states WHERE user_id = ?", (user_id,))
        await db.commit()
                                 
