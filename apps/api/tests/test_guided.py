import pytest
from pydantic import ValidationError

from app.chat.guided import Answer, Back, GuidedState, Skip, advance, budget_note, prompt_for, restriction_note, start, to_filters
from app.models import Near


def walk(texts):
    state, steps = start(), []
    for text in texts:
        steps.append(state.step)
        state = advance(state, Answer(text=text))
    return [*steps, state.step], state


def at(step):
    state = start()
    while state.step != step:
        state = advance(state, Skip())
    return state


def test_full_path_order():
    steps, state = walk(["ขอนแก่น", "4", "100", "อีสาน", "ไม่มี"])
    assert steps == ["place", "party", "budget", "craving", "restriction", "done"]
    f = to_filters(state)
    assert (f.province_code, f.budget_per_person, f.tags) == ("TH-40", 100, ["isan"])


def test_skip_everything_leaves_filters_unset():
    f = to_filters(at("done"))
    assert f.model_dump(exclude_defaults=True) == {}


def test_back_goes_one_step_and_clears_that_answer():
    _, state = walk(["ขอนแก่น", "4", "100"])
    back = advance(state, Back())
    assert back.step == "budget" and back.answers.model_fields_set == {"place", "party"}


def test_back_at_first_step_stays():
    assert advance(start(), Back()).step == "place"


def test_back_from_done_returns_to_restriction():
    assert advance(at("done"), Back()).step == "restriction"


def test_party_only_affects_the_total_note():
    _, state = walk(["ขอนแก่น", "4 คน", "100 บาท"])
    assert budget_note(state) == "งบรวมประมาณ 400 บาทสำหรับ 4 คน"
    assert "party" not in to_filters(state).model_dump()


def test_no_note_without_both_numbers():
    assert budget_note(at("craving")) is None


@pytest.mark.parametrize("step,text", [
    ("party", "0"), ("party", "-1"), ("party", "51"), ("party", "สี่สิบเอ็ดล้าน"), ("party", "4.5"),
    ("budget", "0"), ("budget", "ถูกๆ"), ("budget", "9999999"), ("place", "ดาวอังคาร"), ("place", "ขอนแก่นหรืออุดร"),
    ("place", "   "), ("craving", "   "),
])
def test_unusable_answer_reasks_with_a_reason(step, text):
    state = advance(at(step), Answer(text=text))
    assert state.step == step and state.error and step not in state.answers.model_fields_set


def test_error_clears_after_a_good_answer():
    bad = advance(at("party"), Answer(text="0"))
    assert advance(bad, Answer(text="๔")).error is None


@pytest.mark.parametrize("text,code", [("เลย", "TH-42"), ("โคราช", "TH-30"), ("จังหวัดเลย", "TH-42")])
def test_place_names(text, code):
    assert to_filters(advance(start(), Answer(text=text))).province_code == code


def test_shared_location_becomes_near():
    state = advance(start(), Answer(near=Near(lat=16.43, lon=102.83)))
    assert state.step == "party" and to_filters(state).near.lat == 16.43


def test_location_is_only_accepted_for_place():
    assert advance(at("party"), Answer(near=Near(lat=16, lon=102))).error


def test_unknown_craving_becomes_a_name_term():
    f = to_filters(advance(at("craving"), Answer(text="ปลาร้าบอง")))
    assert f.tags == [] and f.terms == ["ปลาร้าบอง"]


def test_anything_goes_is_a_skip():
    assert to_filters(advance(at("craving"), Answer(text="อะไรก็ได้"))).terms == []


def test_restriction_is_never_a_filter_and_says_to_ask_the_restaurant():
    state = advance(at("restriction"), Answer(text="แพ้กุ้ง"))
    f = to_filters(state)
    assert f.terms == [] and f.tags == []
    assert "แพ้กุ้ง" in restriction_note(state) and "ต้องสอบถามร้านก่อน" in restriction_note(state)
    assert restriction_note(advance(at("restriction"), Answer(text="ไม่มี"))) is None


@pytest.mark.parametrize("step", ["place", "party", "budget", "craving", "restriction"])
def test_every_question_has_text(step):
    p = prompt_for(at(step))
    assert p.text and len(p.options) <= 8


def test_done_has_no_question():
    assert prompt_for(at("done")) is None


@pytest.mark.parametrize("raw", [
    {"step": "budget", "answers": {}}, {"step": "place", "answers": {"party": 4}}, {"step": "done", "answers": {"place": None}},
    {"step": "party", "answers": {"place": "TH-99"}}, {"step": "budget", "answers": {"place": None, "party": 99}},
    {"step": "nope", "answers": {}}, {"step": "place", "answers": {}, "extra": 1},
])
def test_forged_client_state_is_rejected(raw):
    with pytest.raises(ValidationError):
        GuidedState.model_validate(raw)


def test_state_survives_the_round_trip_to_the_browser():
    _, state = walk(["ขอนแก่น", "4", "100", "อีสาน"])
    assert GuidedState.model_validate_json(state.model_dump_json()) == state
