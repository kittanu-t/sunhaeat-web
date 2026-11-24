import hmac
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request

from app.chat.quota import cleanup
from app.db import pool_of

router = APIRouter(prefix="/internal")


@router.get("/cron/daily")
def daily(request: Request) -> dict:
    secret = request.app.state.settings.cron_secret
    given = request.headers.get("authorization", "")
    if not secret or not hmac.compare_digest(given.encode(), f"Bearer {secret}".encode()):
        raise HTTPException(401, "unauthorized")
    with pool_of(request).connection() as conn:
        cleanup(conn, datetime.now(UTC))
        row = conn.execute("select count(*) as restaurants from app.restaurants").fetchone()
    return {"status": "ok", **row}
