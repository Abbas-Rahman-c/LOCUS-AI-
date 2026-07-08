"""
Application lifespan context manager.
Handles startup (DB pool, queue connections) and shutdown teardown.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    yield
    # shutdown
