from app.config import get_settings
from app.database.sessions import engine
from app.models.base import Base
import asyncio

async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

asyncio.run(init())
