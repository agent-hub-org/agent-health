from agent_common.secrets.akv import load_akv_secrets
load_akv_secrets()

import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from agent_common.logging import configure_logging
from agent_common.utils.env import validate_required_env_vars
from agent_common.server.app_factory import create_agent_app
from agents.agent import create_agent
from database.mongo import MongoDB
from a2a_service.server import create_a2a_app

configure_logging("agent_health")
logger = logging.getLogger("agent_health.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from agent_common.observability import init_sentry
    init_sentry("agent-health")
    validate_required_env_vars(
        ["MONGO_URI", "AZURE_AI_FOUNDRY_ENDPOINT", "AZURE_AI_FOUNDRY_API_KEY",
         "MEM0_API_KEY"],
        "agent-health",
    )
    if not os.getenv("INTERNAL_API_KEY"):
        logger.warning("INTERNAL_API_KEY is not set — internal API is unprotected. Set this in production.")
    agent = create_agent()
    try:
        await agent._ensure_initialized()
        if getattr(agent, '_degraded', False):
            logger.warning("Agent started in DEGRADED mode — MCP tools unavailable")
        else:
            logger.info("MCP servers connected, health agent ready")
    except Exception as e:
        logger.error("Agent initialization failed (continuing without MCP): %s", e)
    await MongoDB.ensure_indexes()
    yield
    await agent._disconnect_mcp()
    await MongoDB.close()
    logger.info("Shutdown complete")


app, limiter = create_agent_app("Health & Fitness Agent API", lifespan)

a2a_app = create_a2a_app()
app.mount("/a2a", a2a_app.build())

# Import routers after limiter is defined so `from app import limiter` resolves correctly
from routers.agent import router as agent_router
from routers.history import router as history_router
from routers.profile import router as profile_router
from routers.progress import router as progress_router
from routers.admin import router as admin_router

app.include_router(agent_router)
app.include_router(history_router)
app.include_router(profile_router)
app.include_router(progress_router)
app.include_router(admin_router)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 9005))
    ssl_certfile = os.getenv("SSL_CERTFILE") or None
    ssl_keyfile = os.getenv("SSL_KEYFILE") or None
    uvicorn.run(app, host="0.0.0.0", port=port, ssl_certfile=ssl_certfile, ssl_keyfile=ssl_keyfile)
