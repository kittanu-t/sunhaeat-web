"""Free-text chat: rules first, Gemini only when they are not enough, rules again when Gemini fails."""
import logging
import time
from datetime import UTC, datetime
from typing import Literal

import psycopg
from psycopg_pool import ConnectionPool, PoolTimeout
from pydantic import BaseModel

from app.chat.gemini import MAX_CALLS, GeminiClient, ProviderError, Transport
from app.chat.quota import Limits, block_ai, reserve, settle
from app.models import Filters, Place, SearchResult
from app.search.parse import parse_rules, requires_verified_details
from app.search.repository import search
from app.settings import Settings

log = logging.getLogger("sunhaeat")

TOTAL_DEADLINE_S = 20
CLARIFY = "ลองระบุจังหวัด ประเภทอาหาร หรืองบต่อคน เช่น “ส้มตำขอนแก่น งบ 100”"
ASK_RESTAURANT = ("เรื่องอาหารแพ้ ข้อจำกัดด้านอาหาร ความสะอาด ที่จอดรถ รสชาติ และเวลาเปิด ระบบไม่มีข้อมูลที่ยืนยันได้ "
                  "ต้องสอบถามร้านโดยตรง ลองค้นจากประเภทอาหารหรือจังหวัดแทนได้")
DISCLAIMER = "ข้อมูลร้านจากชุดข้อมูลเปิด ยังไม่ยืนยันว่าร้านเปิดอยู่ ควรตรวจกับร้านก่อนเดินทาง"


class ChatReply(BaseModel):
    mode: Literal["ai", "rules"]
    text: str
    filters: Filters
    result: SearchResult
    disclaimer: str = DISCLAIMER
    partial: bool = False  # some of what was asked could not be applied
    ai_unavailable: Literal["off", "limit", "error"] | None = None  # with mode "ai": understood, but not ranked by AI
    ai_code: str | None = None


def describe(result: SearchResult, partial: bool = False) -> str:
    """Template text only; it never repeats a restaurant name or model output."""
    if result.matched and partial:
        parts = [f"แสดง {len(result.matched)} ร้านจากเงื่อนไขเท่าที่อ่านได้ ยังมีคำขอบางส่วนที่ระบบไม่ได้ใช้กรอง"]
    elif result.matched:
        parts = [f"แสดง {len(result.matched)} ร้านที่ตรงเงื่อนไข"]
        if result.maybe:
            parts.append(f"และอีก {len(result.maybe)} ร้านที่อาจตรงแต่ไม่ทราบราคา")
    elif result.maybe:
        parts = [f"แสดง {len(result.maybe)} ร้านที่อาจตรงแต่ไม่ทราบราคา ควรสอบถามร้านก่อน"]
    else:
        parts = ["ยังไม่พบร้านที่ตรงเงื่อนไข", CLARIFY]
    if result.demo:
        parts.append("ร้านตัวอย่างที่แสดงแยกไว้เป็นร้านสมมติ")
    return " ".join(parts)


def _usable(f: Filters) -> bool:
    return bool(f.name or f.province_code or f.tags or f.budget_per_person)


def rules_for(text: str, history: list[str]) -> Filters:
    """What the user has stated so far; the newest value of each condition wins."""
    current = parse_rules(text)
    if current.name:
        return current
    said: dict = {}
    for earlier in (*map(parse_rules, history), current):
        if earlier.name:
            said = {}
            continue
        stated = {"province_code": earlier.province_code, "tags": earlier.tags, "budget_per_person": earlier.budget_per_person}
        said |= {k: v for k, v in stated.items() if v}
    return current.model_copy(update=said)


def _merge(model: Filters, rules: Filters) -> Filters:
    """The model may add constraints but never relax or replace one the user stated outright."""
    budgets = [b for b in (model.budget_per_person, rules.budget_per_person) if b]
    return model.model_copy(update={
        "name": rules.name or model.name,
        "province_code": rules.province_code or model.province_code,
        "tags": rules.tags or model.tags,
        "budget_per_person": min(budgets) if budgets else None,
    })


def _pick(result: SearchResult, ids: list) -> SearchResult:
    rank = {pid: i for i, pid in enumerate(ids)}

    def chosen(places: list[Place]) -> list[Place]:
        return sorted((p for p in places if p.id in rank), key=lambda p: rank[p.id])

    return SearchResult(matched=chosen(result.matched), maybe=chosen(result.maybe), demo=result.demo)


def _find(pool: ConnectionPool, filters: Filters) -> SearchResult:
    with pool.connection() as conn, conn.cursor() as cur:
        return search(cur, filters)


def _find_with_terms(pool: ConnectionPool, filters: Filters) -> tuple[Filters, SearchResult]:
    """Terms must appear in a place's name; when none does, keep the food type and say the rest was not applied."""
    result = _find(pool, filters)
    if filters.terms and filters.tags and not (result.matched or result.maybe):
        filters = filters.model_copy(update={"terms": [], "needs_clarification": True})
        result = _find(pool, filters)
    return filters, result


def _rules_reply(pool: ConnectionPool, rules: Filters, **why) -> ChatReply:
    if not _usable(rules):
        return ChatReply(mode="rules", text=CLARIFY, filters=rules, result=SearchResult(), **why)
    result = _find(pool, rules)
    partial = rules.needs_clarification
    text = describe(result, partial)
    if partial and CLARIFY not in text:
        text = f"{text} {CLARIFY}"
    return ChatReply(mode="rules", text=text, filters=rules, result=result, partial=partial, **why)


def _stop_if_refused(pool: ConnectionPool, now: datetime, code: str) -> None:
    if code in ("quota", "auth"):
        with pool.connection() as conn:
            block_ai(conn, now)


def answer_free(pool: ConnectionPool, settings: Settings, transport: Transport | None, text: str, history: list[str],
                session: str, ip: str) -> ChatReply:
    reply = _answer(pool, settings, transport, text, history, session, ip)
    if not requires_verified_details(text) and any(map(requires_verified_details, history)):
        # An allergy or similar stated earlier still applies, and still cannot be checked.
        reply = reply.model_copy(update={"partial": True, "text": f"{reply.text} {ASK_RESTAURANT}"})
    return reply


def _answer(pool: ConnectionPool, settings: Settings, transport: Transport | None, text: str, history: list[str],
                session: str, ip: str) -> ChatReply:
    deadline = time.monotonic() + TOTAL_DEADLINE_S
    rules = rules_for(text, history)
    if requires_verified_details(text):
        return ChatReply(mode="rules", text=ASK_RESTAURANT, filters=rules, result=SearchResult())
    if not rules.needs_clarification and not history:
        return _rules_reply(pool, rules)
    if transport is None or not settings.ai_ready:
        return _rules_reply(pool, rules, ai_unavailable="off")

    now = datetime.now(UTC)
    limits = Limits(settings.session_daily_ai, settings.ip_daily_ai, settings.global_daily_ai)
    with pool.connection() as conn:
        reservation = reserve(conn, session, ip, now, limits)
    if reservation is None:
        return _rules_reply(pool, rules, ai_unavailable="limit")

    client = GeminiClient(transport, settings.ai_timeout_s)
    try:
        filters = _merge(client.parse(text, history), rules)
        if not _usable(filters) and not filters.terms:
            return ChatReply(mode="ai", text=CLARIFY, filters=filters, result=SearchResult())
        filters, result = _find_with_terms(pool, filters)
        candidates = result.matched + result.maybe
        unranked = None
        if len(candidates) > 3:
            # Ranking is optional: without it, what the model understood still stands, in database order.
            if client.calls >= MAX_CALLS:
                unranked = "busy"
            elif time.monotonic() + settings.ai_timeout_s >= deadline:
                unranked = "timeout"
            else:
                try:
                    result = _pick(result, client.select(text, candidates))
                except ProviderError as e:
                    unranked = e.code
                    _stop_if_refused(pool, now, e.code)
        return ChatReply(mode="ai", text=describe(result, filters.needs_clarification), filters=filters,
                         result=result, partial=filters.needs_clarification,
                         ai_unavailable="error" if unranked else None, ai_code=unranked)
    except ProviderError as e:
        _stop_if_refused(pool, now, e.code)
        return _rules_reply(pool, rules, ai_unavailable="error", ai_code=e.code)
    finally:
        try:
            with pool.connection() as conn:
                settle(conn, reservation, client.tokens)
        except (psycopg.OperationalError, PoolTimeout):
            log.warning("chat token accounting failed")  # the request itself is already counted
