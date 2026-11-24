from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.settings import Settings


def get_pool(settings: Settings) -> ConnectionPool:
    # prepare_threshold=None: the Supabase transaction pooler cannot keep prepared statements.
    return ConnectionPool(
        settings.database_url, min_size=0, max_size=4, timeout=3, open=False,
        kwargs={"prepare_threshold": None, "row_factory": dict_row, "connect_timeout": 3},
    )
