from ..core.config import settings
from loguru import logger
from psycopg import AsyncConnection
# инициализация под windows:
# python -c "import asyncio; from asyncio import WindowsSelectorEventLoopPolicy;
# asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy()); from app.database.database import init_db;
# asyncio.run(init_db())"
# для устранения проблем с 'ProactorEventLoop' to run in async mode в psycopg работа в асинхронном режиме
# согласно https://docs.python.org/3/library/asyncio-policy.html
# ---------------------------------------------
# Исправляется запуском проекта из под run.py
async def get_db() -> AsyncConnection:
    async with await AsyncConnection.connect(settings.DATABASE_URL) as conn:
        yield conn

async def init_db():
    async with await AsyncConnection.connect(settings.DATABASE_URL) as conn:
        with open("app/database/schema.sql") as f:
            schema = f.read()
        async with conn.cursor() as cur:
            await cur.execute(schema)
            await conn.commit()
        logger.info("Database schema initialized")