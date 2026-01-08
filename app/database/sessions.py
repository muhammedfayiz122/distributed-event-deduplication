from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from app.config import settings

DATABASE_URL = settings.database_url.replace(
    "postgresql://", "postgresql+asyncpg://"
)

engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except:
            await session.rollback()
            raise
