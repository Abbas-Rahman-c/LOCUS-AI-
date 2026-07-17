"""
Locus AI - FastAPI application factory.
Initialises middleware, routers, and the lifespan context.
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.lifespan import lifespan
from modules.auth.router import router as auth_router
from modules.decisions.router import router as decisions_router
from modules.feedback.router import router as feedback_router
from modules.integrations.gmail.router import router as gmail_router
from modules.mcp.server import router as mcp_router
from modules.retrieval.router import router as retrieval_router

app = FastAPI(title="Locus AI", version="0.1.0", lifespan=lifespan)

# -- CORS -----------------------------------------------------------------------
# Default to localhost for development; override via ALLOWED_ORIGINS (comma-sep)
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# -- Routers --------------------------------------------------------------------

# Auth — no authentication required (this IS the auth endpoint)
app.include_router(auth_router)

# Decisions — all routes require JWT auth (enforced inside the router)
app.include_router(decisions_router)

# MCP — all routes require JWT auth (enforced inside the router)
app.include_router(mcp_router)

# Retrieval — QA ask route
app.include_router(retrieval_router)

# Gmail integration & feedback (existing routers)
app.include_router(gmail_router)
app.include_router(feedback_router)
