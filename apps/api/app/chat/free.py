"""Free-text chat: rules first, Gemini only when they are not enough, rules again when Gemini fails."""
import time
from datetime import UTC, datetime
from typing import Literal

from psycopg_pool import ConnectionPool
from pydantic import BaseModel

from app.chat.gemini import GeminiClient, ProviderError, Transport
from app.chat.quota import Limits, block_ai, reserve, settle
from app.models import Filters, Place, SearchResult
from app.search.parse import parse_rules, requires_verified_details
from app.search.repository import search
from app.settings import Settings

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
    ai_unavailable: Literal["off", "limit", "error"] | None = None
    ai_code: str | None = None


def describe(filters: Filters, result: SearchResult) -> str:
    """Template text only; it never repeats a restaurant name or model output."""
    if result.matched:
        parts = [f"พบร้านที่ตรงเงื่อนไข {len(result.matched)} ร้าน"]
        if result.maybe:
            parts.append(f"และอีก {len(result.maybe)} ร้านที่อาจตรงแต่ไม่ทราบราคา")
    elif result.maybe:
        parts = [f"พบ {len(result.maybe)} ร้านที่อาจตรงแต่ไม่ทราบราคา ควรสอบถามร้านก่อน"]
    else:
        parts = ["ยังไม่พบร้านที่ตรงเงื่อนไข", CLARIFY]
    if result.demo:
        parts.append("ร้านตัวอย่างที่แสดงแยกไว้เป็นร้านสมมติ")
    return " ".join(parts)


def _usable(f: Filters) -> bool:
    return bool(f.name or f.province_code or f.tags or f.budget_per_person)


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


def _rules_reply(pool: ConnectionPool, rules: Filters, **why) -> ChatReply:
    if not _usable(rules):
        return ChatReply(mode="rules", text=CLARIFY, filters=rules, result=SearchResult(), **why)
    result = _find(pool, rules)
    text = describe(rules, result)
    if rules.needs_clarification and CLARIFY not in text:
        text = f"{text} {CLARIFY}"
    return ChatReply(mode="rules", text=text, filters=rules, result=result, **why)


def answer_free(pool: ConnectionPool, settings: Settings, transport: Transport | None, text: str, history: list[str],
                session: str, ip: str) -> ChatReply:
    deadline = time.monotonic() + TOTAL_DEADLINE_S
    rules = parse_rules(text)
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
        result = _find(pool, filters)
        candidates = result.matched + result.maybe
        if len(candidates) > 3 and time.monotonic() + settings.ai_timeout_s < deadline:
            result = _pick(result, client.select(text, candidates))
        return ChatReply(mode="ai", text=describe(filters, result), filters=filters, result=result)
    except ProviderError as e:
        if e.code in ("quota", "auth"):
            with pool.connection() as conn:
                block_ai(conn, now)
        return _rules_reply(pool, rules, ai_unavailable="error", ai_code=e.code)
    finally:
        with pool.connection() as conn:
            settle(conn, reservation, client.tokens)
