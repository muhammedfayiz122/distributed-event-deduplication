"""
Database session management for SQLAlchemy with async support.
"""

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from sqlalchemy.pool import StaticPool, NullPool
from app.utils.logger import get_logger

from app.config import settings

logger = get_logger(__name__)

# Create async database engine
# Convert sync URL to async URL if needed
def get_async_database_url():
    sync_url = settings.database_url
    if sync_url.startswith('sqlite:'):
        return sync_url.replace('sqlite:', 'sqlite+aiosqlite:')
    elif sync_url.startswith('postgresql:'):
        return sync_url.replace('postgresql:', 'postgresql+asyncpg:')
    else:
        return sync_url

# Detect if running in Celery worker (event loop conflicts)
is_celery_worker = os.environ.get('CELERY_WORKER_RUNNING') == 'true' or \
                   'celery' in os.environ.get('CELERY_LOADER', '').lower()

# Use NullPool for Celery workers to avoid event loop conflicts
# NullPool creates new connection for each request (no pooling)
# This prevents "Event loop is closed" errors in async + Celery

# Build engine kwargs based on mode
engine_kwargs = {
    # "echo": settings.debug,
    "future": True,
}

if is_celery_worker:
    # NullPool mode: No pooling, no pool-related parameters
    engine_kwargs["poolclass"] = NullPool
else:
    # Default QueuePool mode: Connection pooling with parameters
    engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_recycle": 3600,
        "max_overflow": 20,
        "pool_size": 10,
    })

async_engine = create_async_engine(
    get_async_database_url(),
    **engine_kwargs
)

logger.info(
    f"Async database engine created with {'NullPool (Celery worker mode)' if is_celery_worker else 'default pool (FastAPI mode)'}"
)

# Create async session factory
async_session = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for models
from app.models.base import Base

async def create_tables():
    """Create all database tables asynchronously."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def drop_tables():
    """Drop all database tables asynchronously."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

# Dependency for FastAPI
async def get_async_db_session():
    """
    Get async database session for dependency injection.
    
    Yields:
        AsyncSession: Database session
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# For use outside of FastAPI dependency injection
def get_db_session_context():
    """
    Get async database session context manager.
    
    Returns:
        AsyncSession context manager
    """
    return async_session()

async def test_connection():
    """
    Test database connection asynchronously.
    
    Returns:
        bool: True if connection successful
    """
    try:
        async with async_engine.connect() as connection:
            result = await connection.execute(text("SELECT 1"))
            logger.info("Database connection test successful")
            return True
    except Exception as e:
        logger.error(f"Database connection test failed: {str(e)}")
        raise

async def get_db_info():
    """
    Get database information and statistics asynchronously.
    
    Returns:
        dict: Database information
    """
    try:
        async with async_engine.connect() as connection:
            db_url = get_async_database_url()
            
            if "postgresql" in db_url:
                # Get PostgreSQL version
                result = await connection.execute(text("SELECT version()"))
                version = result.scalar()
                
                # Get database size
                db_name = settings.database_name
                size_result = await connection.execute(
                    text(f"SELECT pg_size_pretty(pg_database_size('{db_name}'))")
                )
                db_size = size_result.scalar()
                
                return {
                    "engine": "PostgreSQL",
                    "version": version,
                    "database_name": db_name,
                    "database_size": db_size,
                }
            elif "sqlite" in db_url:
                # Get SQLite version and info
                result = await connection.execute(text("SELECT sqlite_version()"))
                version = result.scalar()
                
                return {
                    "engine": "SQLite",
                    "version": version,
                    "database_url": db_url,
                }
            else:
                return {
                    "engine": "Unknown",
                    "database_url": db_url,
                }
                
    except Exception as e:
        logger.error(f"Failed to get database info: {str(e)}")
        return {"error": str(e)}

# Event listeners for async engine
from sqlalchemy import event
import time

@event.listens_for(async_engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Set SQLite pragmas for async connections."""
    if "sqlite" in get_async_database_url():
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()
        logger.debug("Set SQLite pragmas for async connection")

# @event.listens_for(async_engine.sync_engine, "before_cursor_execute")
# def before_execute(conn, cursor, statement, parameters, context, executemany):
#     import time
#     context._query_start_time = time.time()

# @event.listens_for(async_engine.sync_engine, "after_cursor_execute")
# def after_execute(conn, cursor, statement, parameters, context, executemany):
#     import time
#     total = time.time() - context._query_start_time
#     if total > 1.0:
#         logger.warning(f"Slow query detected ({total:.2f}s): {statement[:200]}")

if __name__ == "__main__":
    import asyncio
    
    async def main():
        # Test the async session
        async with async_session() as db:
            result = await db.execute(text("SELECT 1"))
            print("Async database test successful:", result.scalar())
        
        # Test connection
        await test_connection()
        
        # Get DB info
        info = await get_db_info()
        print("Database info:", info)
    
    asyncio.run(main())