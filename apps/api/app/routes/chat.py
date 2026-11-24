import json
import logging
import time
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.chat.free import ChatReply, answer_free, describe
from app.chat.guided import Action, GuidedState, Prompt, advance, budget_note, prompt_for, restriction_note, start, to_filters
from app.chat.quota import allow_rate
from app.db import pool_of
from app.models import Strict
from app.search.repository import search

router = APIRouter(prefix="/v1/chat")
log = logging.getLogger("sunhaeat")

FREE_PER_MINUTE = 5
GUIDED_PER_MINUTE = 30
IP_FACTOR = 4  # sessions are cheap to create, so an IP gets a few sessions' worth

Message = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class FreeRequest(Strict):
    text: Message
    history: list[Message] = Field(default_factory=list, max_length=6)


class GuidedRequest(Strict):
    state: GuidedState | None = None
    action: Action | None = None

    @model_validator(mode="after")
    def both_or_neither(self):
        if (self.state is None) != (self.action is None):
            raise ValueError("state and action go together")
        return self


class GuidedResponse(BaseModel):
    state: GuidedState
    prompt: Prompt | None
    reply: ChatReply | None


def _rate_limit(request: Request, kind: str, per_minute: int) -> None:
    now = datetime.now(UTC)
    with pool_of(request).connection() as conn:
        allowed = (allow_rate(conn, f"{kind}:s:{request.state.session}", per_minute, now)
                   and allow_rate(conn, f"{kind}:ip:{request.state.ip}", per_minute * IP_FACTOR, now))
    if not allowed:
        raise HTTPException(429, "rate_limited")


@router.post("/free")
def free(request: Request, body: FreeRequest) -> ChatReply:
    _rate_limit(request, "free", FREE_PER_MINUTE)
    started = time.monotonic()
    state = request.app.state
    reply = answer_free(pool_of(request), state.settings, state.transport, body.text, body.history,
                        request.state.session, request.state.ip)
    # Codes and timings only: no message, identity or coordinates.
    log.info("chat %s", json.dumps({"mode": reply.mode, "ai_unavailable": reply.ai_unavailable, "ai_code": reply.ai_code,
                                    "latency_ms": round((time.monotonic() - started) * 1000)}))
    return reply


@router.post("/guided")
def guided(request: Request, body: GuidedRequest) -> GuidedResponse:
    _rate_limit(request, "guided", GUIDED_PER_MINUTE)
    state = start() if body.state is None else advance(body.state, body.action)
    reply = None
    if state.step == "done":
        filters = to_filters(state)
        with pool_of(request).connection() as conn, conn.cursor() as cur:
            result = search(cur, filters)
        text = " ".join(filter(None, [describe(result), budget_note(state), restriction_note(state)]))
        reply = ChatReply(mode="rules", text=text, filters=filters, result=result)
    return GuidedResponse(state=state, prompt=prompt_for(state), reply=reply)
