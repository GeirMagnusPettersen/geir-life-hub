from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import auth, coffee, devices, fluids, health_observations, kitchenowl, reports, sleep_activity, weight

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Schema creation/evolution is handled by Alembic migrations
    # (`alembic upgrade head`), run before the app starts (see the
    # Dockerfile CMD and README "Database migrations" section), so no
    # table creation happens here at app startup.
    yield


app = FastAPI(title="Geir Life Hub API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(devices.router)
app.include_router(weight.router)
app.include_router(fluids.router)
app.include_router(coffee.router)
app.include_router(health_observations.router)
app.include_router(sleep_activity.router)
app.include_router(reports.router)
app.include_router(kitchenowl.router)
