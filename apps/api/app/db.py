from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from psycopg import Cursor
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.settings import Settings


def get_pool(settings: Settings) -> ConnectionPool:
    # prepare_threshold=None: the Supabase transaction pooler cannot keep prepared statements.
    return ConnectionPool(
        settings.database_url, min_size=0, max_size=4, timeout=3, open=False,
        kwargs={"prepare_threshold": None, "row_factory": dict_row, "connect_timeout": 3},
    )


def pool_of(request: Request) -> ConnectionPool:
    pool: ConnectionPool = request.app.state.pool
    pool.open()  # no-op once open; lazy because serverless hosts may skip ASGI startup
    return pool


def _cursor(request: Request) -> Iterator[Cursor]:
    with pool_of(request).connection() as conn, conn.cursor() as cur:
        yield cur


Cur = Annotated[Cursor, Depends(_cursor)]
