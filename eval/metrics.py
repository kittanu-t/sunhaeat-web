"""Evaluation metrics. A slot is right only when its whole value matches."""
import math

SLOTS = ("name", "province_code", "tags", "budget_per_person")


def _value(slot: str, value):
    return frozenset(value) if slot == "tags" else value


def _f1(tp: int, fp: int, fn: int) -> float | None:
    return None if tp + fp + fn == 0 else 2 * tp / (2 * tp + fp + fn)


def slot_f1(gold: list[dict], pred: list[dict]) -> dict:
    """micro pools every slot; macro averages F1 over the slots that occur in gold or prediction."""
    if len(gold) != len(pred):
        raise ValueError("gold and predictions differ in length")
    counts = {slot: [0, 0, 0] for slot in SLOTS}
    for g, p in zip(gold, pred, strict=True):
        for slot, c in counts.items():
            want, got = g.get(slot) or None, p.get(slot) or None
            hit = want is not None and got is not None and _value(slot, want) == _value(slot, got)
            c[0] += hit
            c[1] += got is not None and not hit
            c[2] += want is not None and not hit
    tp, fp, fn = (sum(c[i] for c in counts.values()) for i in range(3))
    per_slot = {slot: score for slot, c in counts.items() if (score := _f1(*c)) is not None}
    return {
        "precision": tp / (tp + fp) if tp + fp else None, "recall": tp / (tp + fn) if tp + fn else None,
        "micro": _f1(tp, fp, fn), "macro": sum(per_slot.values()) / len(per_slot) if per_slot else None, "per_slot": per_slot,
        "support": tp + fn,
    }


def recall_at_k(gold: list[str], ranked: list[list[str]], k: int) -> float:
    return sum(g in r[:k] for g, r in zip(gold, ranked, strict=True)) / len(gold)


def constraint_violations(filters: dict, places: list[dict]) -> int:
    """Shown places that break a constraint the system itself says it applied."""
    province, tags, budget = filters.get("province_code"), set(filters.get("tags") or []), filters.get("budget_per_person")
    bad = 0
    for p in places:
        demo = p["lane"] == "demo"
        over = budget is not None and p["price_max"] is not None and p["price_max"] > budget
        unconfirmed = budget is not None and p["price_max"] is None and p["lane"] != "maybe"
        wrong_place = province is not None and not demo and p["province_code"] != province
        wrong_food = bool(tags) and not tags & set(p["tags"])
        bad += demo != p["is_demo"] or over or unconfirmed or wrong_place or wrong_food
    return bad


def gold_violations(gold: dict, places: list[dict]) -> int:
    """Shown places that break what the question really asked, whatever the system understood."""
    return constraint_violations(gold, places)


def percentile(values: list[float], p: int) -> float | None:
    if not values:
        return None
    return sorted(values)[max(0, math.ceil(p / 100 * len(values)) - 1)]
