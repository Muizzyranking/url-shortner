import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.core import cache as cache_module
from app.db import postgres as database
from app.db import redis as redis_module
from app.main import app


@pytest.fixture(autouse=True)
async def _test_db():
    engine = create_async_engine(settings.DB_URL, poolclass=NullPool)
    session_local = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    database.engine = engine
    database.AsyncSessionLocal = session_local

    async with engine.begin() as conn:
        await conn.run_sync(database.Base.metadata.create_all)

    yield

    async with engine.begin() as conn:
        await conn.run_sync(database.Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(autouse=True)
async def _test_redis():
    redis_module._redis = None
    redis = cache_module.get_redis()
    await redis.flushdb()
    yield
    await redis.aclose()
    redis_module._redis = None


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
