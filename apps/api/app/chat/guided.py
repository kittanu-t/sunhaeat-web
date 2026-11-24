"""Question-by-question recommendation. Needs no language model; state lives in the browser and is re-validated here."""
import re
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_serializer, model_validator

from app.models import Filters, Near, ProvinceCode, Strict
from app.search.parse import parse_budget, provinces_in, to_arabic_digits
from app.search.tags import LABELS, tags_in

STEPS = ("place", "party", "budget", "craving", "restriction", "done")
Step = Literal["place", "party", "budget", "craving", "restriction", "done"]
Text = Annotated[str, Field(min_length=1, max_length=60)]


class Answers(Strict):
    place: ProvinceCode | Near | None = None
    party: Annotated[int, Field(ge=1, le=50)] | None = None
    budget: Annotated[int, Field(ge=1, le=100_000)] | None = None
    craving: Text | None = None
    restriction: Text | None = None

    @model_serializer(mode="wrap")
    def only_answered(self, handler):
        # A skipped question is present as null; an unasked one must stay absent.
        return {k: v for k, v in handler(self).items() if k in self.model_fields_set}


class GuidedState(Strict):
    step: Step = "place"
    answers: Answers = Field(default_factory=Answers)
    error: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def answered_exactly_the_earlier_steps(self):
        if self.answers.model_fields_set != set(STEPS[:STEPS.index(self.step)]):
            raise ValueError("answers do not match step")
        return self


class Answer(Strict):
    type: Literal["answer"] = "answer"
    text: str | None = Field(default=None, max_length=100)
    near: Near | None = None


class Skip(Strict):
    type: Literal["skip"] = "skip"


class Back(Strict):
    type: Literal["back"] = "back"


Action = Annotated[Answer | Skip | Back, Field(discriminator="type")]


class Prompt(BaseModel):
    text: str
    options: list[str]


class Unusable(Exception):
    pass


def start() -> GuidedState:
    return GuidedState()


def _number(text: str, unit: str) -> int | None:
    m = re.fullmatch(rf"(\d[\d,]*)\s*(?:{unit})?", to_arabic_digits(text).strip())
    return int(m[1].replace(",", "")) if m else None


def _read(step: str, answer: Answer):
    if answer.near is not None:
        if step != "place":
            raise Unusable("ใช้ตำแหน่งได้เฉพาะคำถามเรื่องพื้นที่")
        return answer.near
    text = (answer.text or "").strip()
    if not text:
        raise Unusable("พิมพ์คำตอบ เลือกตัวเลือก หรือกดข้าม")
    if step == "place":
        found = provinces_in(text)
        if len(found) != 1:
            raise Unusable("เลือกหนึ่งจังหวัดในภาคอีสาน เช่น ขอนแก่น หรือกดข้าม")
        return found[0]
    if step == "party":
        n = _number(text, "คน")
        if n is None or not 1 <= n <= 50:
            raise Unusable("ระบุจำนวนคน 1–50 เช่น 4")
        return n
    if step == "budget":
        n = _number(text, "บาท") or parse_budget(text)
        if n is None or not 1 <= n <= 100_000:
            raise Unusable("ระบุงบต่อคนเป็นตัวเลข เช่น 100")
        return n
    if step == "craving":
        return None if text in ("อะไรก็ได้", "ไม่มี") else text[:60]
    return None if text in ("ไม่มี", "ไม่มีข้อจำกัด") else text[:60]


def _with(state: GuidedState, step: str, values: dict, error: str | None = None) -> GuidedState:
    return GuidedState(step=step, answers=Answers(**values), error=error)


def advance(state: GuidedState, action: Answer | Skip | Back) -> GuidedState:
    values = {k: getattr(state.answers, k) for k in state.answers.model_fields_set}
    i = STEPS.index(state.step)
    if isinstance(action, Back):
        i = max(i - 1, 0)
        values.pop(STEPS[i], None)
        return _with(state, STEPS[i], values)
    if state.step == "done":
        return state
    if isinstance(action, Skip):
        value = None
    else:
        try:
            value = _read(state.step, action)
        except Unusable as e:
            return _with(state, state.step, values, str(e))
    return _with(state, STEPS[i + 1], values | {state.step: value})


_QUESTIONS = {
    "place": ("อยากกินแถวไหน?", ["ขอนแก่น", "นครราชสีมา", "อุดรธานี", "อุบลราชธานี", "บุรีรัมย์", "สกลนคร"]),
    "party": ("ไปกันกี่คน?", ["1", "2", "4", "6"]),
    "budget": ("งบต่อคนประมาณเท่าไร?", ["60", "100", "200", "400"]),
    "craving": ("อยากกินอะไร?", [LABELS[t] for t in ("isan", "noodle", "hotpot_grill", "coffee", "rice_made_to_order", "japanese")]
                + ["อะไรก็ได้"]),
    "restriction": ("มีข้อจำกัดไหม เช่น แพ้อาหารหรือฮาลาล?", ["ไม่มี", "แพ้อาหารทะเล", "ฮาลาล", "มังสวิรัติ"]),
}


def prompt_for(state: GuidedState) -> Prompt | None:
    if state.step == "done":
        return None
    text, options = _QUESTIONS[state.step]
    return Prompt(text=text, options=options)


def to_filters(state: GuidedState) -> Filters:
    a = state.answers
    tags = tags_in(a.craving) if a.craving else []
    return Filters(
        province_code=a.place if isinstance(a.place, str) else None,
        near=a.place if isinstance(a.place, Near) else None,
        budget_per_person=a.budget,
        tags=tags,
        terms=[a.craving] if a.craving and not tags else [],
    )


def budget_note(state: GuidedState) -> str | None:
    a = state.answers
    if a.party and a.budget:
        return f"งบรวมประมาณ {a.party * a.budget:,} บาทสำหรับ {a.party} คน"
    return None


def restriction_note(state: GuidedState) -> str | None:
    if state.answers.restriction:
        return f"ข้อจำกัด “{state.answers.restriction}” ต้องสอบถามร้านก่อน ระบบไม่มีข้อมูลที่ยืนยันได้"
    return None
