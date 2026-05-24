from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.observability import init_observability
from app.core.database import connect_db, disconnect_db
from app.api.v1.router import api_router

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_observability()
    await connect_db()
    yield
    await disconnect_db()


app = FastAPI(
    title="RegAI Compliance Agent",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
