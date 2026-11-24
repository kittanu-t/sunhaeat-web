"""Evaluate chat on a labelled split.

From the repository root, PYTHONPATH="apps/api;.", DATABASE_URL set to a database holding the built dataset:
    python -m eval.run --system rules --split dev
    python -m eval.run --system gemini --split dev --max-calls 300     (needs GEMINI_API_KEY and GEMINI_MODEL; uses your quota)
Tune on dev only. Run test once per system, after a person has checked the gold labels.
"""
import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
import time
from datetime import UTC, datetime

from app.chat.free import answer_free
from app.chat.gemini import SdkTransport
from app.db import get_pool
from app.settings import Settings
from eval.metrics import constraint_violations, percentile, recall_at_k, slot_f1

ROOT = pathlib.Path(__file__).parents[1]
QUESTIONS = ROOT / "eval/questions.jsonl"


class OutOfCalls(Exception):
    pass


class CallBudget:
    def __init__(self, limit: int):
        self.limit, self.used = limit, 0

    def spend(self) -> None:
        if self.used >= self.limit:
            raise OutOfCalls
        self.used += 1


class CountingTransport:
    def __init__(self, inner, budget: CallBudget):
        self.inner, self.budget, self.tokens, self.codes = inner, budget, 0, []

    def generate(self, system, payload, schema):
        self.budget.spend()
        text, tokens = self.inner.generate(system, payload, schema)
        self.tokens += tokens
        return text, tokens


def load(split: str) -> list[dict]:
    rows = [json.loads(line) for line in QUESTIONS.read_text(encoding="utf8").splitlines()]
    return [r for r in rows if r["split"] == split]


def shown(reply) -> list[dict]:
    return [p.model_dump(mode="json") | {"lane": lane} for lane in ("matched", "maybe", "demo") for p in getattr(reply.result, lane)]


def ask(pool, settings, transport, question) -> dict:
    started = time.perf_counter()
    reply = answer_free(pool, settings, transport, question["text"], question.get("history", []), "eval", "eval")
    return {"id": question["id"], "group": question["group"], "mode": reply.mode, "ai_code": reply.ai_code, "text": reply.text,
            "filters": reply.filters.model_dump(mode="json"), "places": shown(reply),
            "latency_ms": (time.perf_counter() - started) * 1000}


def exact_rate(pairs) -> float:
    """Share of questions whose every slot is right."""
    return sum(slot_f1([q["gold"]], [a["filters"]])["micro"] in (None, 1.0) for q, a in pairs) / len(pairs)


def score(questions: list[dict], answers: list[dict]) -> dict:
    by_group = {g: [(q, a) for q, a in zip(questions, answers, strict=True) if q["group"] == g]
                for g in ("slots", "retrieval", "abstain", "injection")}
    report: dict = {"n": len(answers), "n_by_group": {g: len(v) for g, v in by_group.items()}}
    if pairs := by_group["slots"]:
        report["slots"] = slot_f1([q["gold"] for q, _ in pairs], [a["filters"] for _, a in pairs])
        report["slots"]["exact_question_rate"] = exact_rate(pairs)
    if pairs := by_group["retrieval"]:
        gold = [q["gold_slug"] for q, _ in pairs]
        ranked = [[p["slug"] for p in a["places"] if p["lane"] != "demo"] for _, a in pairs]
        report["retrieval"] = {f"recall@{k}": recall_at_k(gold, ranked, k) for k in (1, 5)}
    if pairs := by_group["abstain"]:
        report["abstain_rate"] = sum(not a["places"] for _, a in pairs) / len(pairs)
    if pairs := by_group["injection"]:
        report["injection_slots_exact"] = exact_rate(pairs)
    report["constraint_violations"] = sum(constraint_violations(a["filters"], a["places"]) for a in answers)
    report["modes"] = {m: sum(a["mode"] == m for a in answers) for m in ("ai", "rules")}
    report["ai_errors"] = {c: sum(a["ai_code"] == c for a in answers) for c in sorted({a["ai_code"] for a in answers if a["ai_code"]})}
    report["latency_ms"] = {f"p{p}": percentile([a["latency_ms"] for a in answers], p) for p in (50, 95)}
    return report


def main() -> None:
    sys.stdout.reconfigure(encoding="utf8")
    args = argparse.ArgumentParser()
    args.add_argument("--system", choices=["rules", "gemini"], required=True)
    args.add_argument("--split", choices=["dev", "test"], required=True)
    args.add_argument("--max-calls", type=int, default=300)
    o = args.parse_args()
    huge = {"session_daily_ai": 10_000, "ip_daily_ai": 10_000, "global_daily_ai": 10_000}
    settings = Settings(_env_file=None, **huge)
    transport = None
    budget = CallBudget(o.max_calls)
    if o.system == "gemini":
        settings = settings.model_copy(update={"ai_enabled": "true"})
        if not settings.ai_ready:
            raise SystemExit("set GEMINI_API_KEY and GEMINI_MODEL")
        transport = CountingTransport(SdkTransport(settings.gemini_api_key, settings.gemini_model, settings.ai_timeout_s), budget)
    questions, answers, complete = load(o.split), [], True
    with get_pool(settings) as pool:
        for q in questions:
            try:
                answers.append(ask(pool, settings, transport, q))
            except OutOfCalls:
                complete = False
                break
    manifest = json.loads((ROOT / "data/build/manifest.json").read_text(encoding="utf8"))
    git = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)  # noqa: S607
    report = {
        "system": o.system, "split": o.split, "complete": complete, "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": git.stdout.strip(), "model": settings.gemini_model if o.system == "gemini" else None, "dataset_sha256": manifest["sha256"],
        "questions_sha256": hashlib.sha256(QUESTIONS.read_bytes()).hexdigest(), "calls": budget.used,
        "tokens": transport.tokens if transport else 0, **score(questions[:len(answers)], answers),
    }
    out = ROOT / "eval/results"
    out.mkdir(exist_ok=True)
    (out / f"{o.system}-{o.split}.json").write_text(
        json.dumps({"report": report, "answers": answers}, ensure_ascii=False, indent=1), encoding="utf8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
