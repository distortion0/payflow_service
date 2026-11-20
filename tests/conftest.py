import json
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.config import Settings
from app.db import create_tables
from app.events import process_event
from app.main import create_app
from app.models import metadata
from app.schemas import Envelope, Outcome

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://payflow:payflow@localhost:5432/payflow_test"
)
HAPPY_PATH = Path(__file__).parent / "data" / "happy_path.json"

Deliver = Callable[[dict[str, Any]], Awaitable[Outcome | None]]


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
def engine(app: FastAPI) -> AsyncEngine:
    return app.state.engine


@pytest.fixture
async def conn(engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    async with engine.connect() as conn:
        yield conn


@pytest.fixture
def deliver(engine: AsyncEngine) -> Deliver:
    """Process one raw event the way a webhook request would: on its own connection."""

    async def _deliver(event: dict[str, Any]) -> Outcome | None:
        async with engine.connect() as conn:
            return await process_event(conn, Envelope.model_validate(event))

    return _deliver


@pytest.fixture
def happy_path() -> list[dict[str, Any]]:
    return json.loads(HAPPY_PATH.read_text())


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
