"""
Standalone asyncpg connectivity diagnostic — bypasses FastAPI/uvicorn entirely.

Used to isolate a Windows SSL-handshake failure to the network path rather
than the app: confirms whether a bare asyncpg.connect() against the
Supabase pooler succeeds independent of any application code.

Usage:
    cd backend
    poetry run python test_db_connection.py
"""
import asyncio
import os
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import asyncpg
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


async def test():
    dsn = os.environ["APP_DATABASE_URL"]
    conn = await asyncpg.connect(dsn)
    result = await conn.fetchval('SELECT 1')
    print('SUCCESS:', result)
    await conn.close()

asyncio.run(test())