"""Deterministic Thai query parser. Anything it cannot verify becomes needs_clarification, never a guess."""
import re

from app.models import Filters
from app.search.normalize import canonical_thai
from app.search.tags import tags_in, without_tag_words

PROVINCES: dict[str, tuple[str, ...]] = {
    "TH-30": ("นครราชสีมา", "โคราช", "ปากช่อง", "เขาใหญ่"), "TH-31": ("บุรีรัมย์",), "TH-32": ("สุรินทร์",),
    "TH-33": ("ศรีสะเกษ", "ศรีษะเกษ"), "TH-34": ("อุบลราชธานี", "อุบล"), "TH-35": ("ยโสธร",), "TH-36": ("ชัยภูมิ",),
    "TH-37": ("อำนาจเจริญ",), "TH-38": ("บึงกาฬ",), "TH-39": ("หนองบัวลำภู",),
    "TH-40": ("ขอนแก่น", "มข.", "ม.ขอนแก่น", "หลังมอ", "กังสดาล", "โนนม่วง", "บึงแก่นนคร"),
    "TH-41": ("อุดรธานี", "อุดร"), "TH-42": ("เชียงคาน",), "TH-43": ("หนองคาย",), "TH-44": ("มหาสารคาม", "สารคาม", "มมส"),
    "TH-45": ("ร้อยเอ็ด",), "TH-46": ("กาฬสินธุ์",), "TH-47": ("สกลนคร", "สกล"), "TH-48": ("นครพนม",), "TH-49": ("มุกดาหาร",),
}
# "เลย" is also an everyday particle, so it only counts as a province after a place word.
_LOEI = re.compile(r"(?:จังหวัด|จ\.|เมือง|แถว|ใน|ที่|อยู่)\s*เลย(?![ก-๎])")
_REGION = re.compile(r"(?:ภาค|แถว|แถบ|ใน|เมือง|แดน)\s*อีสาน")
_UNVERIFIABLE = re.compile(
    r"แพ้|มังสวิรัติ|วีแกน|ฮาลาล|อาหารเจ|กินเจ|vegan|vegetarian|halal|gluten|allerg|ที่จอดรถ|อร่อย(?:ที่)?สุด|ปลอดภัย|สะอาด"
    r"|ไม่(?:เผ็ด|หวาน|มัน|เค็ม|ใส่|เอา|กิน|มี|ใช้)|งด|ยกเว้น|เปิด(?:อยู่|ตอน|กี่|ถึง|ทุกวัน|วัน|ดึก|หลัง|บ้าง|เช้า|\s*24)"
    r"|24\s*(?:ชั่วโมง|ชม)|ปิดกี่|ตอนนี้เปิด", re.IGNORECASE)
_NAME = re.compile(r"^(?:ขอข้อมูลร้าน|ข้อมูลร้าน|ค้นหาร้าน|หาร้านชื่อ)\s*(.+)$")
# The upper end of a range, and never a distance, a duration or a head count.
_AMOUNT = (r"(?:\d{1,6}\s*[-–]\s*)?(\d{1,6})(?![\d.])"
           r"(?!\s*(?:กม|กิโล|km|เมตร|ม\.|นาที|ชั่วโมง|ชม|คน|ร้าน))")
_BUDGET = (re.compile(rf"(?:งบ(?:รวม)?|ราคา)\s*(?:ไม่เกิน|ประมาณ|สัก|แค่)?\s*{_AMOUNT}"),
           re.compile(rf"(?:ไม่เกิน|คนละ)\s*(?:ไม่เกิน)?\s*{_AMOUNT}"),
           re.compile(rf"{_AMOUNT}\s*บาท"))
_PARTY = re.compile(r"(\d{1,2})\s*คน")
_VAGUE_BUDGET = re.compile(r"งบ|ราคา|บาท|ถูก ?ๆ")
_THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")


def to_arabic_digits(text: str) -> str:
    return text.translate(_THAI_DIGITS)


def _tidy(text: str) -> str:
    text = canonical_thai(to_arabic_digits(text)).casefold()
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)
    return re.sub(r"\s+", " ", text).strip()


def requires_verified_details(text: str) -> bool:
    return bool(_UNVERIFIABLE.search(_tidy(text)))


def provinces_in(text: str) -> list[str]:
    tidy = _tidy(text)
    found = [code for code, names in PROVINCES.items() if any(n in tidy for n in names)]
    if "TH-42" not in found and (_LOEI.search(tidy) or tidy == "เลย"):
        found.append("TH-42")
    return found


def parse_budget(text: str) -> int | None:
    """Baht per person, or None when no usable amount is stated."""
    tidy = _tidy(text)
    for rule in _BUDGET:
        if m := rule.search(tidy):
            amount = int(m[1])
            party = _PARTY.search(tidy)
            if "รวม" in tidy and party and int(party[1]) > 0:
                amount //= int(party[1])
            return amount if 1 <= amount <= 100_000 else None
    return None


# Words that carry no condition. Anything else left over is something the rules did not read.
_FILLER = sorted((
    "อยากจะ อยาก กิน ทาน หาร้าน หา ร้านอาหาร ร้าน อาหาร เมนู แถวๆ แถว แถบ ย่าน ใกล้ๆ บริเวณ ที่ไหน ที่ ใน จังหวัด จ. อำเภอ อ. เมือง "
    "มีไหม ไหม มั้ย มี ไหน บ้าง ขอเป็น ขอ เป็น เอา แนะนำ ช่วย ให้หน่อย ให้ หน่อย อะไรดี อะไร ดี กับ และ หรือ แล้ว ก็ได้ ก็ ได้ ไปกัน ไป กัน มา "
    "งบรวม งบคนละ งบ ต่อคน คนละ คน ละ บาท ราคา ไม่เกิน เกิน ประมาณ สัก แค่ รวม ครับ ค่ะ คะ ค่า จ้า จ้ะ นะ ด้วย เลย มาก หิวข้าว หิว วันนี้ "
    "นี้ นั้น แบบ สำหรับ เรา ผม ฉัน หนู in at a the please want find near food restaurant").split(), key=len, reverse=True)
_FILLER_RULE = re.compile("|".join(map(re.escape, _FILLER)))


def _unread(tidy: str) -> bool:
    """True when words or numbers remain after removing everything the parser understood."""
    rest = _REGION.sub(" ", tidy)
    for rule in (*_BUDGET, _PARTY, _LOEI):
        rest = rule.sub(" ", rest)
    for name in sorted((n for names in PROVINCES.values() for n in names), key=len, reverse=True):
        rest = rest.replace(name, " ")
    rest = _FILLER_RULE.sub(" ", without_tag_words(rest))
    return bool(re.search(r"\d", rest)) or len(re.findall(r"[ก-๎a-z]", rest)) >= 3


def parse_rules(text: str) -> Filters:
    tidy = _tidy(text)
    if m := _NAME.match(tidy):
        return Filters(name=m[1][:100], needs_clarification=requires_verified_details(tidy))
    provinces = provinces_in(tidy)
    budget = parse_budget(tidy)
    tags = tags_in(_REGION.sub(" ", tidy))
    unclear = (
        len(provinces) > 1
        or (budget is None and bool(_VAGUE_BUDGET.search(tidy)))
        or requires_verified_details(tidy)
        or not (provinces or tags or budget)
        or _unread(tidy)
    )
    return Filters(province_code=provinces[0] if len(provinces) == 1 else None, tags=tags, budget_per_person=budget,
                   needs_clarification=unclear)
