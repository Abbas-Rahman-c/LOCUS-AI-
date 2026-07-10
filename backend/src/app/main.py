"""
Locus AI - FastAPI application factory.
Initialises middleware, routers, and the lifespan context.
"""
from fastapi import FastAPI
from app.lifespan import lifespan
from modules.integrations.gmail.router import router as gmail_router

app = FastAPI(title="Locus AI", version="0.1.0", lifespan=lifespan)

# Register integration routers
app.include_router(gmail_router)
