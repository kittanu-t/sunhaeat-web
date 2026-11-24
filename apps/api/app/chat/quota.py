"""Rate limits and daily AI budget, enforced atomically in Postgres."""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from psycopg import Connection, Rollback

BANGKOK = ZoneInfo("Asia/Bangkok")


@dataclass(frozen=True)
class Limits:
    session: int
    ip: int
    everyone: int


@dataclass(frozen=True)
class Reservation:
    day: date
    scopes: tuple[str, ...]


def _day(now: datetime) -> date:
    return now.astimezone(BANGKOK).date()


def reserve(conn: Connection, session: str, ip: str, now: datetime, limits: Limits) -> Reservation | None:
    """Count one AI message against all three limits, or against none of them."""
    # Fixed order (global first) so concurrent requests cannot deadlock.
    scopes = (("global", limits.everyone), (f"ip:{ip}", limits.ip), (f"s:{session}", limits.session))
    if min(limit for _, limit in scopes) <= 0:
        return None
    day = _day(now)
    with conn.transaction() as tx:
        for scope, limit in scopes:
            counted = conn.execute(
                """insert into app.ai_usage as u (day, scope, requests) values (%s, %s, 1)
                   on conflict (day, scope) do update set requests = u.requests + 1
                   where u.requests < %s and not u.blocked returning 1""", [day, scope, limit]).fetchone()
            if counted is None:
                raise Rollback(tx)
        return Reservation(day, tuple(scope for scope, _ in scopes))
    return None


def settle(conn: Connection, reservation: Reservation, tokens: int | None) -> None:
    """Record tokens. The request stays counted whatever happened to the call."""
    if tokens:
        conn.execute("update app.ai_usage set tokens = tokens + %s where day = %s and scope = any(%s)",
                     [tokens, reservation.day, list(reservation.scopes)])


def block_ai(conn: Connection, now: datetime) -> None:
    conn.execute("""insert into app.ai_usage (day, scope, blocked) values (%s, 'global', true)
        on conflict (day, scope) do update set blocked = true""", [_day(now)])


def allow_rate(conn: Connection, key: str, per_minute: int, now: datetime) -> bool:
    window = now.replace(second=0, microsecond=0)
    return conn.execute(
        """insert into app.rate_limits as r (key, window_start, hits) values (%s, %s, 1)
           on conflict (key, window_start) do update set hits = r.hits + 1 where r.hits < %s returning 1""",
        [key, window, per_minute]).fetchone() is not None


def cleanup(conn: Connection, now: datetime) -> None:
    conn.execute("delete from app.rate_limits where window_start < %s", [now - timedelta(days=2)])
    conn.execute("delete from app.ai_usage where day < %s", [_day(now) - timedelta(days=30)])
