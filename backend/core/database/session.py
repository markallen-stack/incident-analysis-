"""
Database session management for PostgreSQL.
"""
from dotenv import load_dotenv
load_dotenv()  # loads variables from .env


import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from typing import AsyncGenerator
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.database.models import Base
from sqlalchemy.engine import URL
import os

USER = os.getenv("DB_USER")
PASSWORD = os.getenv("DB_PASSWORD")
HOST = os.getenv("DB_HOST")
PORT = int(os.getenv("DB_PORT"))
DBNAME = os.getenv("DB_NAME")

# Sanity check
print(USER, PASSWORD, HOST, PORT, DBNAME)


DATABASE_URL = URL.create(
    drivername="postgresql+asyncpg",
    username=USER,
    password=PASSWORD,       # handles @ safely
    host=HOST,
    port=PORT,
    database=DBNAME,
    # query={"sslmode": "require"},
)

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using
    pool_size=5,
    max_overflow=10,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI to get database session.
    Usage:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """
    Initialize database: create all tables.
    Run this once on startup or via migration script.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database tables created")


async def drop_db():
    """
    Drop all tables (use with caution!).
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("⚠️  All database tables dropped")
