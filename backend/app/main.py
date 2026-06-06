from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401
from app.api import (
    admin_custom_block_reviews,
    auth,
    backtests,
    custom_blocks,
    health,
    shared_blocks,
    simulation_accounts,
    strategies,
)
from app.core.config import get_settings
from app.core.database import Base, engine

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if settings.environment == "development":
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(admin_custom_block_reviews.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(backtests.router, prefix="/api")
app.include_router(custom_blocks.router, prefix="/api")
app.include_router(shared_blocks.router, prefix="/api")
app.include_router(simulation_accounts.router, prefix="/api")
app.include_router(strategies.router, prefix="/api")
