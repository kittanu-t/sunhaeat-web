import psycopg
import pytest

CATALOG = ["provinces", "restaurants", "restaurant_sources", "menu_items", "opening_hours"]
USAGE = ["rate_limits", "ai_usage"]


@pytest.mark.parametrize("role", ["anon", "authenticated"])
@pytest.mark.parametrize("table", CATALOG + USAGE)
def test_public_roles_see_nothing(db, role, table):
    with db.as_role(role), pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.execute(f"select 1 from app.{table}")


@pytest.mark.parametrize("table", CATALOG)
def test_runtime_reads_but_cannot_write_catalog(db, table):
    with db.as_role("api_runtime"):
        db.execute(f"select 1 from app.{table}")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute(f"delete from app.{table}")


def test_runtime_sees_catalog_rows_through_rls(db):
    db.execute("insert into app.provinces(code,name_th) values ('TH-40','ขอนแก่น')")
    with db.as_role("api_runtime"):
        assert db.scalar("select count(*) from app.provinces") == 1


@pytest.mark.parametrize("sql", [
    "insert into app.rate_limits(key,window_start,hits) values ('s',now(),1)",
    "insert into app.ai_usage(day,scope,requests) values (current_date,'global',1)",
])
def test_runtime_writes_usage(db, sql):
    with db.as_role("api_runtime"):
        assert db.execute(sql).rowcount == 1


def test_every_app_table_has_rls(db):
    assert db.scalar("select count(*) from pg_tables where schemaname='app' and not rowsecurity") == 0
    assert db.scalar("select count(*) from pg_tables where schemaname='app'") == len(CATALOG + USAGE)


def test_thai_trigrams_exist(db):
    assert db.scalar("select cardinality(show_trgm('ส้มตำ'))") > 0


def test_runtime_role_has_no_elevated_privileges(db):
    flags = "select rolsuper or rolcreaterole or rolbypassrls from pg_roles where rolname = 'api_runtime'"
    assert db.scalar(flags) is False
