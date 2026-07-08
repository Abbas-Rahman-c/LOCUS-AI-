"""
Locus AI — FastAPI application factory.
Initialises middleware, routers, and the lifespan context.
"""
from fastapi import FastAPI
from app.lifespan import lifespan

app = FastAPI(title="Locus AI", version="0.1.0", lifespan=lifespan)
