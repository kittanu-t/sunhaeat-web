"""Fold a person's review of the gold labels back into eval/questions.jsonl.

The review page saves one JSON document per question. Export them, then from the repository root:
    python -m eval.apply_review <folder of review documents>
Questions corrected only with a note (a wrong restaurant, an abstain that should answer) are listed and stay unreviewed
until someone edits them by hand.
"""
import json
import pathlib
import sys

from eval.run import QUESTIONS

STATUSES = ("ok", "fix", "drop")


def apply(rows: list[dict], reviews: dict[str, dict]) -> tuple[list[dict], list[str]]:
    """New rows in the same order, and the ids that still need a hand edit."""
    known = {r["id"] for r in rows}
    if unknown := sorted(set(reviews) - known):
        raise ValueError(f"reviews for unknown questions: {unknown}")
    out, pending = [], []
    for row in rows:
        review = reviews.get(row["id"])
        if review is None:
            out.append(row)
            continue
        status = review.get("status")
        if status not in STATUSES:
            raise ValueError(f"{row['id']}: unknown status {status!r}")
        new = dict(row)
        if note := (review.get("note") or "").strip():
            new["review_note"] = note
        if status == "drop":
            new |= {"reviewed_by_human": True, "excluded": True}
        elif status == "ok":
            new["reviewed_by_human"] = True
        elif "gold" in review:
            new["gold"] = {k: v for k, v in review["gold"].items() if v not in (None, [], "")}
            new["reviewed_by_human"] = True
        else:
            new["reviewed_by_human"] = False
            pending.append(row["id"])
        out.append(new)
    return out, pending


def main(folder: str) -> None:
    sys.stdout.reconfigure(encoding="utf8")
    reviews = {}
    for path in sorted(pathlib.Path(folder).rglob("*.json")):
        doc = json.loads(path.read_text(encoding="utf8"))
        reviews[path.stem] = doc.get("data", doc)  # an export may wrap the body with its id and version
    rows = [json.loads(line) for line in QUESTIONS.read_text(encoding="utf8").splitlines()]
    rows, pending = apply(rows, reviews)
    QUESTIONS.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf8", newline="\n")
    reviewed = sum(r["reviewed_by_human"] for r in rows)
    print(f"applied {len(reviews)} reviews; {reviewed}/{len(rows)} reviewed; excluded {sum(r.get('excluded', False) for r in rows)}")
    if pending:
        print("needs a hand edit:", ", ".join(pending))


if __name__ == "__main__":
    main(sys.argv[1])
