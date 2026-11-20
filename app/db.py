from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from app.models import metadata


def make_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url)


async def create_tables(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)


async def get_connection(request: Request) -> AsyncIterator[AsyncConnection]:
    """Transactions are opened by the code that needs them: ``async with conn.begin()``."""
    engine: AsyncEngine = request.app.state.engine
    async with engine.connect() as conn:
        yield conn


ConnectionDep = Annotated[AsyncConnection, Depends(get_connection)]
