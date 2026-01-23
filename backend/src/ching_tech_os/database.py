"""資料庫連線管理"""

import json
import asyncpg
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from .config import settings

_pool: asyncpg.Pool | None = None


async def _setup_json_codec(conn: asyncpg.Connection) -> None:
    """設定 JSON/JSONB 類型的編解碼器"""
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )
    await conn.set_type_codec(
        "json",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


async def init_db_pool() -> None:
    """初始化資料庫連線池"""
    global _pool
    _pool = await asyncpg.create_pool(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        min_size=2,
        max_size=10,
        init=_setup_json_codec,  # 每個連線建立時自動設定 JSON 編解碼器
    )


async def close_db_pool() -> None:
    """關閉資料庫連線池"""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    """取得資料庫連線池"""
    if _pool is None:
        raise RuntimeError("Database pool not initialized")
    return _pool


@asynccontextmanager
async def get_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """取得資料庫連線"""
    pool = get_pool()
    async with pool.acquire() as conn:
        yield conn
