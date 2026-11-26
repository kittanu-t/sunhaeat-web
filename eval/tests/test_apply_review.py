import pytest

from eval.apply_review import apply
from eval.run import usable

Q = [
    {"id": "slots-1", "split": "dev", "reviewed_by_human": False, "group": "slots", "text": "x", "gold": {"province_code": "TH-40"}},
    {"id": "retrieval-1", "split": "test", "reviewed_by_human": False, "group": "retrieval", "text": "y", "gold_slug": "a"},
    {"id": "abstain-1", "split": "test", "reviewed_by_human": False, "group": "abstain", "text": "z"},
]


def test_confirmed_question_is_marked_reviewed_and_unreviewed_ones_stay_as_they_were():
    rows, pending = apply(Q, {"slots-1": {"status": "ok"}})
    assert rows[0] == Q[0] | {"reviewed_by_human": True} and rows[1:] == Q[1:] and pending == []


def test_corrected_slots_replace_the_gold_without_empty_values():
    fix = {"status": "fix", "gold": {"province_code": None, "tags": ["isan"], "budget_per_person": 80}, "note": "ไม่ได้บอกจังหวัด"}
    row = apply(Q, {"slots-1": fix})[0][0]
    assert row["gold"] == {"tags": ["isan"], "budget_per_person": 80} and row["reviewed_by_human"] and row["review_note"] == "ไม่ได้บอกจังหวัด"


def test_a_correction_written_only_as_a_note_waits_for_a_hand_edit():
    rows, pending = apply(Q, {"retrieval-1": {"status": "fix", "note": "ร้านนี้ไม่ใช่ร้านอาหาร"}})
    assert rows[1]["reviewed_by_human"] is False and rows[1]["review_note"] == "ร้านนี้ไม่ใช่ร้านอาหาร" and pending == ["retrieval-1"]


def test_dropped_question_is_kept_for_the_record_but_never_evaluated():
    rows, _ = apply(Q, {"abstain-1": {"status": "drop"}})
    assert rows[2]["excluded"] is True and rows[2]["reviewed_by_human"] is True
    assert [r["id"] for r in rows if usable(r, "test")] == ["retrieval-1"]


@pytest.mark.parametrize("reviews", [{"nope-1": {"status": "ok"}}, {"slots-1": {"status": "maybe"}}])
def test_unknown_question_or_status_is_an_error(reviews):
    with pytest.raises(ValueError):
        apply(Q, reviews)
