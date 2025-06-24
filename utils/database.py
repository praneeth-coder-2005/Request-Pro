import asyncio
import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import DATABASE_URL, STATE_TIMEOUT_SECONDS
from loguru import logger as loguru_logger

Base = declarative_base()

# Define UserState model
class UserState(Base):
    __tablename__ = "user_states"
    user_id = Column(Integer, primary_key=True)
    state = Column(String)
    data = Column(String)  # Store JSON string of additional state data
    last_update = Column(DateTime, default=datetime.datetime.now)

    def __repr__(self):
        return f"<UserState(user_id={self.user_id}, state='{self.state}', last_update='{self.last_update}')>"

# Use AsyncEngine for async database operations
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession
)

async def init_db():
    """Initializes the database, creating tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    loguru_logger.info("Database initialized.")

async def set_user_state(user_id: int, state: str, data: dict = None):
    """Sets or updates the state and associated data for a user."""
    async with AsyncSessionLocal() as session:
        user_state = await session.get(UserState, user_id)
        if user_state:
            user_state.state = state
            user_state.data = str(data) if data else None
            user_state.last_update = datetime.datetime.now()
        else:
            user_state = UserState(user_id=user_id, state=state, data=str(data) if data else None)
            session.add(user_state)
        await session.commit()
        await session.refresh(user_state)
        loguru_logger.debug(f"User {user_id} state set to: {state}")
        return user_state

async def get_user_state(user_id: int):
    """Retrieves the current state and data for a user."""
    async with AsyncSessionLocal() as session:
        user_state = await session.get(UserState, user_id)
        if user_state and (datetime.datetime.now() - user_state.last_update).total_seconds() > STATE_TIMEOUT_SECONDS:
            loguru_logger.debug(f"User {user_id} state expired. Clearing.")
            await clear_user_state(user_id)
            return None, None # Return None if expired
        if user_state:
            data = eval(user_state.data) if user_state.data else {} # Safely evaluate string to dict
            return user_state.state, data
        return None, None

async def clear_user_state(user_id: int):
    """Clears the state for a specific user."""
    async with AsyncSessionLocal() as session:
        user_state = await session.get(UserState, user_id)
        if user_state:
            await session.delete(user_state)
            await session.commit()
            loguru_logger.debug(f"User {user_id} state cleared.")

async def clear_all_expired_states():
    """Periodically clears expired user states from the database."""
    while True:
        await asyncio.sleep(STATE_TIMEOUT_SECONDS) # Check every STATE_TIMEOUT_SECONDS
        async with AsyncSessionLocal() as session: # Use AsyncSessionLocal
            try:
                # Calculate cutoff time once
                cutoff_time = datetime.datetime.now() - datetime.timedelta(seconds=STATE_TIMEOUT_SECONDS)

                # Delete states older than cutoff_time
                result = await session.execute(
                    text("DELETE FROM user_states WHERE last_update < :cutoff_time"),
                    {"cutoff_time": cutoff_time}
                )
                await session.commit()
                loguru_logger.info(f"Cleared {result.rowcount} expired user states.")
            except Exception as e:
                loguru_logger.error(f"Error clearing expired states: {e}", exc_info=True)

