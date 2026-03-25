"""FastAPI entry point for Xuan-Flow."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from xuan_flow.api.routers import chat, management

load_dotenv()

# Filter out frequent polling logs to keep the console clean
class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Skip routine GET requests for management and workspace metadata
        msg = record.getMessage()
        if "GET /api/management/" in msg or "GET /api/workspace/" in msg or "GET /health" in msg:
            return False
        return True

# Apply filter to uvicorn access logs
logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

# Ensure xuan_flow internal logs are shown at INFO level
logging.getLogger("xuan_flow").setLevel(logging.INFO)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: preload things if necessary
    logger.info("Xuan-Flow API starting up...")
    
    # Preload the Lead Agent to ensure config is valid and MCP tools are loaded early
    from xuan_flow.agents.lead_agent import make_lead_agent
    try:
        await make_lead_agent()
        logger.info("Lead Agent preloaded successfully")
    except Exception as e:
        logger.error("Failed to preload Lead Agent: %s", e)
        
    yield
    # Shutdown
    logger.info("Xuan-Flow API shutting down...")


app = FastAPI(
    title="Xuan-Flow API",
    description="Gateway API for the Xuan-Flow Multi-Agent System",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(management.router, prefix="/api/management", tags=["management"])
from xuan_flow.api.routers import workspace
app.include_router(workspace.router, prefix="/api/workspace", tags=["workspace"])


@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "agent": "Xuan-Flow"}
