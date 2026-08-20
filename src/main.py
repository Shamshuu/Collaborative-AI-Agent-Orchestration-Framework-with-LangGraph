from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from src.api.v1.router import api_v1_router
from src.api.websockets import ws_router
from src.config.settings import settings
from src.db.session import async_engine, init_db
from src.redis_client.client import redis_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager to initialize database and connections."""
    logger.info("Initializing database schema...")
    try:
        await init_db()
        logger.info("Database schema initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
    yield
    logger.info("Shutting down application...")
    await async_engine.dispose()


app = FastAPI(
    title="Collaborative AI Agent Orchestration Framework",
    description="Multi-Agent Orchestration Framework with LangGraph, Celery, Redis, PostgreSQL, and WebSockets",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for web frontend clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", status_code=status.HTTP_200_OK, tags=["Health"])
async def health_check():
    """
    Health check endpoint for Docker Compose and load balancer monitoring.
    Verifies connectivity to PostgreSQL and Redis.
    """
    health_status = {
        "status": "healthy",
        "database": "unknown",
        "redis": "unknown",
    }

    # Verify Database connectivity
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            health_status["database"] = "connected"
    except Exception as e:
        health_status["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"

    # Verify Redis connectivity
    try:
        ping = await redis_client.async_client.ping()
        if ping:
            health_status["redis"] = "connected"
    except Exception as e:
        health_status["redis"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"

    return health_status


# Include Routers
app.include_router(api_v1_router)
app.include_router(ws_router)
