from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from psycopg.rows import dict_row

from app.chat.quota import Limits, allow_rate, block_ai, cleanup, reserve, settle

NOW = datetime(2026, 11, 24, 5, 0, tzinfo=UTC)
LIMITS = Limits(session=2, ip=3, everyone=4)


def use(db, session="s1", ip="i1", now=NOW, limits=LIMITS):
    with psycopg.connect(db.url, row_factory=dict_row) as conn:
        return reserve(conn, session, ip, now, limits)


def used(db, scope="global"):
    return db.scalar("select coalesce(max(requests), 0) from app.ai_usage where scope = %s", [scope])


def test_session_limit(db):
    assert [bool(use(db)) for _ in range(3)] == [True, True, False]


def test_ip_limit_spans_sessions(db):
    assert [bool(use(db, session=f"s{i}")) for i in range(4)] == [True, True, True, False]


def test_global_limit_spans_ips(db):
    assert [bool(use(db, session=f"s{i}", ip=f"i{i}")) for i in range(5)] == [True] * 4 + [False]


def test_refused_reservation_leaves_no_partial_counts(db):
    for i in range(3):
        use(db, session=f"s{i}")
    use(db, session="s9")  # refused by IP
    assert used(db) == 3 and used(db, "s:s9") == 0


@pytest.mark.parametrize("limits", [Limits(0, 9, 9), Limits(9, 0, 9), Limits(9, 9, 0)])
def test_zero_limit_means_never(db, limits):
    assert use(db, limits=limits) is None and used(db) == 0


def test_ten_concurrent_reservations_with_one_left(db):
    for i in range(3):
        use(db, session=f"a{i}", ip=f"b{i}")
    with ThreadPoolExecutor(10) as pool:
        got = list(pool.map(lambda i: bool(use(db, session=f"c{i}", ip=f"d{i}")), range(10)))
    assert sum(got) == 1 and used(db) == 4


def test_failed_call_keeps_the_request_counted(db):
    r = use(db)
    with psycopg.connect(db.url) as conn:
        settle(conn, r, None)
    assert used(db) == 1 and db.scalar("select sum(tokens) from app.ai_usage") == 0


def test_settle_records_tokens_once_per_scope(db):
    r = use(db)
    with psycopg.connect(db.url) as conn:
        settle(conn, r, 120)
    assert db.scalar("select tokens from app.ai_usage where scope = 'global'") == 120


def test_block_lasts_until_the_next_bangkok_day(db):
    with psycopg.connect(db.url) as conn:
        block_ai(conn, NOW)
    assert use(db) is None
    assert use(db, now=datetime(2026, 11, 24, 16, 59, tzinfo=UTC)) is None  # 23:59 in Bangkok
    assert use(db, now=datetime(2026, 11, 24, 17, 0, tzinfo=UTC))  # 00:00 in Bangkok


def test_rate_window(db):
    with psycopg.connect(db.url) as conn:
        got = [allow_rate(conn, "k", 5, NOW + timedelta(seconds=i)) for i in range(6)]
        assert got == [True] * 5 + [False]
        assert allow_rate(conn, "k", 5, NOW + timedelta(seconds=60))
        assert allow_rate(conn, "other", 5, NOW)


def test_cleanup_removes_only_old_rows(db):
    with psycopg.connect(db.url) as conn:
        allow_rate(conn, "old", 5, NOW - timedelta(days=3))
        allow_rate(conn, "new", 5, NOW)
        reserve(conn, "s", "i", NOW - timedelta(days=31), LIMITS)
        reserve(conn, "s", "i", NOW, LIMITS)
        cleanup(conn, NOW)
    assert db.scalar("select count(*) from app.rate_limits") == 1
    assert db.scalar("select count(distinct day) from app.ai_usage") == 1
