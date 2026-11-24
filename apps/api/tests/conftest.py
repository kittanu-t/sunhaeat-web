import contextlib
import os
import pathlib

import psycopg
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
TABLES = ["restaurants", "provinces", "rate_limits", "ai_usage"]


class Db:
    def __init__(self, url):
        self.url = url
        self.conn = psycopg.connect(url, autocommit=True)

    def execute(self, sql, params=None):
        return self.conn.execute(sql, params)

    def scalar(self, sql, params=None):
        return self.execute(sql, params).fetchone()[0]

    @contextlib.contextmanager
    def as_role(self, role):
        self.execute(f"set role {role}")
        try:
            yield self
        finally:
            self.execute("reset role")


@pytest.fixture(scope="session")
def database_url():
    if url := os.environ.get("TEST_DATABASE_URL"):
        yield url
        return
    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer("postgis/postgis:17-3.5", driver=None) as pg:
        yield pg.get_connection_url()


@pytest.fixture(scope="session")
def migrated_url(database_url):
    with psycopg.connect(database_url, autocommit=True) as c:
        # Supabase provides these roles; plain Postgres does not.
        for role in ("anon", "authenticated"):
            c.execute(f"do $$ begin create role {role} nologin; exception when duplicate_object then null; end $$")
        for path in sorted((ROOT / "supabase/migrations").glob("*.sql")):
            c.execute(path.read_text(encoding="utf8"))
        c.execute(f'alter database "{c.info.dbname}" set search_path = app, extensions, public')
    return database_url


@pytest.fixture
def db(migrated_url):
    d = Db(migrated_url)
    d.execute("truncate " + ",".join(f"app.{t}" for t in TABLES) + " cascade")
    yield d
    d.conn.close()
