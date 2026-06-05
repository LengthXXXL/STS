from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, backtests, health, simulation_accounts, strategies
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(backtests.router, prefix="/api")
app.include_router(simulation_accounts.router, prefix="/api")
app.include_router(strategies.router, prefix="/api")
