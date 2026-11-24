import pytest

from app.search.parse import parse_rules, requires_verified_details


def test_full_sentence():
    f = parse_rules("อยากกินส้มตำแถวขอนแก่น งบไม่เกิน 100 บาทต่อคน")
    assert (f.province_code, f.tags, f.budget_per_person) == ("TH-40", ["isan"], 100)
    assert not f.needs_clarification


@pytest.mark.parametrize("text,code", [
    ("คาเฟ่โคราช", "TH-30"), ("หมูกระทะหลังมอ", "TH-40"), ("ซูชิ มข.", "TH-40"), ("ก๋วยเตี๋ยวอุบล", "TH-34"),
    ("ร้านกาแฟจังหวัดเลย", "TH-42"), ("กาแฟแถวเลย", "TH-42"), ("ของหวานสกลนคร", "TH-47"),
])
def test_province(text, code):
    assert parse_rules(text).province_code == code


@pytest.mark.parametrize("text", ["อยากกินส้มตำมากเลย", "หิวเลย ก๋วยเตี๋ยว"])
def test_particle_loei_is_not_the_province(text):
    assert parse_rules(text).province_code is None


def test_two_provinces_ask_back():
    assert parse_rules("ส้มตำขอนแก่นหรืออุดร").needs_clarification


@pytest.mark.parametrize("text,budget", [
    ("ส้มตำ งบ 80", 80), ("ส้มตำ ไม่เกิน ๑๕๐ บาท", 150), ("บุฟเฟ่ต์ราคาไม่เกิน 1,000 บาท", 1000),
    ("กาแฟ 60 บาท", 60), ("หมูกระทะงบรวม 1000 บาท 4 คน", 250), ("หมูกระทะ 4 คน งบรวม 1000", 250),
])
def test_budget(text, budget):
    assert parse_rules(text).budget_per_person == budget


@pytest.mark.parametrize("text", ["ส้มตำราคาถูก", "กาแฟงบน้อย", "ส้มตำงบ 0 บาท"])
def test_vague_budget_asks_back(text):
    f = parse_rules(text)
    assert f.needs_clarification and f.budget_per_person is None


def test_region_word_is_not_a_cuisine():
    assert parse_rules("ร้านกาแฟในภาคอีสาน").tags == ["coffee"]


def test_explicit_name():
    f = parse_rules("ขอข้อมูลร้าน ตำคับเอ")
    assert f.name == "ตำคับเอ" and f.tags == [] and not f.needs_clarification


@pytest.mark.parametrize("text", ["", "   ", "สวัสดี", "???"])
def test_nothing_usable_asks_back(text):
    assert parse_rules(text).needs_clarification


@pytest.mark.parametrize("text", [
    "ร้านไหนปลอดภัยสำหรับคนแพ้ถั่ว", "ส้มตำไม่เผ็ด", "ร้านฮาลาลขอนแก่น", "ร้านกาแฟเปิดตอนนี้", "ที่จอดรถเยอะ", "อาหารเจขอนแก่น",
])
def test_unverifiable_requests(text):
    assert requires_verified_details(text) and parse_rules(text).needs_clarification


@pytest.mark.parametrize("text", ["ร้านเจ๊แดง", "ส้มตำขอนแก่น", "ร้านกาแฟโคราช"])
def test_ordinary_requests_are_not_flagged(text):
    assert not requires_verified_details(text)
