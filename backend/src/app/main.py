"""
Locus AI - FastAPI application factory.
Initialises middleware, routers, and the lifespan context.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.lifespan import lifespan
from modules.integrations.gmail.router import router as gmail_router
from modules.feedback.router import router as feedback_router
from modules.retrieval.router import router as retrieval_router

app = FastAPI(title="Locus AI", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register integration routers
app.include_router(gmail_router)

# Register feedback loop router (Phase 3 — Rebira)
app.include_router(feedback_router)

# Register retrieval/RAG router (/retrieval/query, /retrieval/status)
app.include_router(retrieval_router)
