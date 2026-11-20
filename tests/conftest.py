import os
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.config import Settings
from app.db import create_tables
from app.main import create_app
from app.models import metadata

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://payflow:payflow@localhost:5432/payflow_test"
)


async def truncate_all(engine: AsyncEngine) -> None:
    tables = ", ".join(table.name for table in metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables}"))


@pytest.fixture
def settings() -> Settings:
    return Settings(database_url=TEST_DATABASE_URL, payflow_webhook_secret="whsec_test_123")


@pytest.fixture
async def app(settings: Settings) -> AsyncIterator[FastAPI]:
    app = create_app(settings)
    await create_tables(app.state.engine)
    await truncate_all(app.state.engine)
    yield app
    await app.state.engine.dispose()


@pytest.fixture
async def conn(app: FastAPI) -> AsyncIterator[AsyncConnection]:
    async with app.state.engine.connect() as conn:
        yield conn


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
