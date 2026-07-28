"""
Locus AI - Uvicorn entry point.
Run locally: uvicorn main:app --reload --port 8000
"""
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import os
# Add src directory to PYTHONPATH / sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
import uvicorn
from app.main import app
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)