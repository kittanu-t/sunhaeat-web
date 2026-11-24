import pytest

from eval.metrics import constraint_violations, percentile, recall_at_k, slot_f1
from eval.run import CallBudget, OutOfCalls, ran_fully

GOLD = [{"tags": ["isan"], "province_code": "TH-40"}, {"budget_per_person": 100}]
PRED = [{"tags": ["isan"]}, {}]


def test_slot_f1_by_hand():
    s = slot_f1(GOLD, PRED)
    assert (s["precision"], s["recall"], s["micro"]) == (1.0, pytest.approx(1 / 3), pytest.approx(0.5))
    assert s["macro"] == pytest.approx(1 / 3)
    assert s["per_slot"] == {"tags": 1.0, "province_code": 0.0, "budget_per_person": 0.0}


def test_wrong_value_counts_as_both_a_miss_and_a_false_alarm():
    s = slot_f1([{"budget_per_person": 100}], [{"budget_per_person": 200}])
    assert (s["precision"], s["recall"], s["micro"]) == (0.0, 0.0, 0.0)


def test_invented_slot_lowers_precision_only():
    s = slot_f1([{"tags": ["isan"]}], [{"tags": ["isan"], "budget_per_person": 50}])
    assert (s["precision"], s["recall"]) == (0.5, 1.0)


def test_tag_order_does_not_matter_but_the_set_must_match():
    assert slot_f1([{"tags": ["a", "b"]}], [{"tags": ["b", "a"]}])["micro"] == 1.0
    assert slot_f1([{"tags": ["a", "b"]}], [{"tags": ["a"]}])["micro"] == 0.0


def test_nothing_to_find_and_nothing_found_is_not_a_score():
    assert slot_f1([{}], [{}])["micro"] is None


def test_length_mismatch_is_an_error():
    with pytest.raises(ValueError):
        slot_f1([{}], [])


def test_recall_at_k():
    assert recall_at_k(["a", "b", "c"], [["a", "x"], ["x", "y", "b"], []], k=2) == pytest.approx(1 / 3)
    assert recall_at_k(["a", "b", "c"], [["a", "x"], ["x", "y", "b"], []], k=3) == pytest.approx(2 / 3)


def place(**kw):
    return {"slug": "s", "province_code": "TH-40", "tags": ["isan"], "price_max": None, "is_demo": False, "lane": "matched"} | kw


@pytest.mark.parametrize("bad", [
    place(province_code="TH-30"), place(tags=["coffee"]), place(price_max=200), place(is_demo=True), place(lane="matched", price_max=None),
])
def test_each_violation_is_counted(bad):
    filters = {"province_code": "TH-40", "tags": ["isan"], "budget_per_person": 100}
    assert constraint_violations(filters, [bad]) == 1


def test_good_rows_do_not_violate():
    filters = {"province_code": "TH-40", "tags": ["isan", "noodle"], "budget_per_person": 100}
    rows = [place(price_max=90), place(lane="maybe"), place(lane="demo", is_demo=True, province_code="TH-30", price_max=90)]
    assert constraint_violations(filters, rows) == 0


def test_percentile_is_nearest_rank():
    assert percentile([4, 1, 3, 2], 50) == 2 and percentile([4, 1, 3, 2], 95) == 4 and percentile([], 50) is None


def test_call_budget_stops_and_reports_incomplete():
    budget = CallBudget(2)
    budget.spend()
    budget.spend()
    with pytest.raises(OutOfCalls):
        budget.spend()
    assert budget.used == 2


@pytest.mark.parametrize("answer", [{"ai_unavailable": "limit", "ai_code": None}, {"ai_unavailable": "error", "ai_code": "quota"},
                                    {"ai_unavailable": "off", "ai_code": None}, {"ai_unavailable": "error", "ai_code": "auth"}])
def test_a_gemini_run_that_lost_the_model_is_incomplete(answer):
    good = {"ai_unavailable": None, "ai_code": None}
    assert ran_fully("gemini", [good, {"ai_unavailable": "error", "ai_code": "schema"}])
    assert not ran_fully("gemini", [good, answer])
    assert ran_fully("rules", [answer])


def test_dropping_a_stated_budget_is_a_violation_against_gold():
    from eval.metrics import gold_violations

    gold = {"province_code": "TH-40", "budget_per_person": 100}
    shown = [place(price_max=None, lane="matched")]
    assert constraint_violations({"province_code": "TH-40"}, shown) == 0  # self-consistent, yet wrong
    assert gold_violations(gold, shown) == 1
    assert gold_violations(gold, [place(price_max=None, lane="maybe")]) == 0
