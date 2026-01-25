"""Database utilities for batch operations."""

from __future__ import annotations

from typing import Optional

import asyncpg

from config.settings import get_settings

_pool: Optional[asyncpg.Pool] = None


async def get_pool(min_size: int = 2, max_size: int = 10) -> asyncpg.Pool:
    """Get or create a connection pool for database operations.

    This provides better performance than creating individual connections
    for each operation, especially in batch processing scenarios.

    Args:
        min_size: Minimum number of connections to maintain in the pool.
        max_size: Maximum number of connections allowed in the pool.

    Returns:
        An asyncpg connection pool.
    """
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = await asyncpg.create_pool(
            settings.supabase_db_url,
            min_size=min_size,
            max_size=max_size,
        )
    return _pool


async def close_pool() -> None:
    """Close the connection pool.

    Should be called when the application is shutting down.
    """
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def get_connection() -> asyncpg.Connection:
    """Get a single database connection.

    For one-off operations where a pool isn't needed.
    Caller is responsible for closing the connection.

    Returns:
        An asyncpg connection.
    """
    settings = get_settings()
    return await asyncpg.connect(settings.supabase_db_url)
