import aiosqlite
import logging

DB_NAME = "bot.db"
logger = logging.getLogger(__name__)

async def init_db():
    conn = await aiosqlite.connect(DB_NAME)
    async with conn.cursor() as cursor:
        # Create movie_requests table
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS movie_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                user_name TEXT NOT NULL,
                tmdb_id INTEGER NOT NULL,
                tmdb_title TEXT NOT NULL,
                tmdb_overview TEXT,
                tmdb_poster_path TEXT,
                request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending',
                admin_message_id INTEGER,
                original_user_request_msg_id INTEGER,
                channel_message_id INTEGER,  -- NEW: Stores the message ID in the channel
                fulfilled_link TEXT          -- NEW: Stores the permalink to the message or direct URL
            )
        ''')
        # Create user_states table
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_states (
                user_id INTEGER PRIMARY KEY,
                state TEXT NOT NULL,
                data TEXT
            )
        ''')
        await conn.commit()
        logger.info("Database initialized (movie_requests & user_states tables).")
    await conn.close()

async def set_user_state(user_id: int, state: str, data: dict = None):
    conn = await aiosqlite.connect(DB_NAME)
    async with conn.cursor() as cursor:
        await cursor.execute(
            "INSERT OR REPLACE INTO user_states (user_id, state, data) VALUES (?, ?, ?)",
            (user_id, state, str(data))
        )
        await conn.commit()
        logger.debug(f"User {user_id} state set to '{state}' with data {data}")
    await conn.close()

async def get_user_state(user_id: int):
    conn = await aiosqlite.connect(DB_NAME)
    async with conn.cursor() as cursor:
        await cursor.execute("SELECT state, data FROM user_states WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
    await conn.close()
    if row:
        state, data_str = row
        try:
            data = eval(data_str) # Safely evaluate string to dict/list
        except (SyntaxError, TypeError):
            data = {} # Fallback if data is malformed
        return state, data
    return None, {}

async def clear_user_state(user_id: int):
    conn = await aiosqlite.connect(DB_NAME)
    async with conn.cursor() as cursor:
        await cursor.execute("DELETE FROM user_states WHERE user_id = ?", (user_id,))
        await conn.commit()
        logger.debug(f"User {user_id} state cleared.")
    await conn.close()

async def add_movie_request(request_data: dict):
    conn = await aiosqlite.connect(DB_NAME)
    async with conn.cursor() as cursor:
        await cursor.execute(
            """
            INSERT INTO movie_requests (user_id, user_name, tmdb_id, tmdb_title, tmdb_overview, tmdb_poster_path, original_user_request_msg_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_data.get("user_id"),
                request_data.get("user_name"),
                request_data.get("tmdb_id"),
                request_data.get("tmdb_title"),
                request_data.get("tmdb_overview"),
                request_data.get("tmdb_poster_path"),
                request_data.get("original_user_request_msg_id")
            )
        )
        await conn.commit()
        request_id = cursor.lastrowid
        logger.info(f"Movie request added with ID: {request_id} for user {request_data.get('user_id')}")
        return request_id
    await conn.close()

async def get_request_by_id(request_id: int):
    conn = await aiosqlite.connect(DB_NAME)
    async with conn.cursor() as cursor:
        await cursor.execute(
            "SELECT id, user_id, user_name, tmdb_id, tmdb_title, tmdb_overview, tmdb_poster_path, "
            "request_date, status, admin_message_id, original_user_request_msg_id, "
            "channel_message_id, fulfilled_link FROM movie_requests WHERE id = ?",
            (request_id,)
        )
        row = await cursor.fetchone()
    await conn.close()
    if row:
        columns = [description[0] for description in cursor.description]
        return dict(zip(columns, row))
    return None

async def get_request_by_tmdb_id(tmdb_id: int):
    conn = await aiosqlite.connect(DB_NAME)
    async with conn.cursor() as cursor:
        # Fetch the latest fulfilled request for this TMDB ID
        await cursor.execute(
            "SELECT id, user_id, user_name, tmdb_id, tmdb_title, tmdb_overview, tmdb_poster_path, "
            "request_date, status, admin_message_id, original_user_request_msg_id, "
            "channel_message_id, fulfilled_link FROM movie_requests WHERE tmdb_id = ? AND status = 'fulfilled' AND channel_message_id IS NOT NULL ORDER BY id DESC LIMIT 1",
            (tmdb_id,)
        )
        row = await cursor.fetchone()
    await conn.close()
    if row:
        columns = [description[0] for description in cursor.description]
        return dict(zip(columns, row))
    return None

async def update_request_status(request_id: int, status: str, fulfilled_link: str = None):
    conn = await aiosqlite.connect(DB_NAME)
    async with conn.cursor() as cursor:
        if fulfilled_link:
            await cursor.execute(
                "UPDATE movie_requests SET status = ?, fulfilled_link = ? WHERE id = ?",
                (status, fulfilled_link, request_id)
            )
        else:
            await cursor.execute(
                "UPDATE movie_requests SET status = ? WHERE id = ?",
                (status, request_id)
            )
        await conn.commit()
        logger.info(f"Updated request {request_id} status to '{status}'. Link: {fulfilled_link}")
    await conn.close()

async def update_request_admin_message_id(request_id: int, admin_message_id: int):
    conn = await aiosqlite.connect(DB_NAME)
    async with conn.cursor() as cursor:
        await cursor.execute(
            "UPDATE movie_requests SET admin_message_id = ? WHERE id = ?",
            (admin_message_id, request_id)
        )
        await conn.commit()
        logger.info(f"Updated request {request_id} with admin_message_id: {admin_message_id}")
    await conn.close()

async def update_movie_channel_id(request_id: int, channel_msg_id: int):
    conn = await aiosqlite.connect(DB_NAME)
    async with conn.cursor() as cursor:
        await cursor.execute(
            "UPDATE movie_requests SET channel_message_id = ? WHERE id = ?",
            (channel_msg_id, request_id)
        )
        await conn.commit()
        logger.info(f"Updated request {request_id} with channel_message_id: {channel_msg_id}")
    await conn.close()
                                   
