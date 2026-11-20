"""Run with: uvicorn app.main:create_app --factory"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.config import Settings
from app.db import ConnectionDep, create_tables, make_engine


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await create_tables(engine)
        yield
        await engine.dispose()

    app = FastAPI(title="PayFlow card operations", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine

    @app.get("/health")
    async def health(conn: ConnectionDep) -> dict[str, str]:
        await conn.execute(text("SELECT 1"))
        return {"status": "ok"}

    return app
