import pytest

from pipeline.tagging import TAGS, clean_text, slug_for, tags_for


@pytest.mark.parametrize("name,tax,expected", [
    ("ก๊วยเตี๋ยวเป็ดตุ๋นยาจีน", "ramen_restaurant", ["noodle"]),
    ("โจ๊กหม้อไฟชัยภูมิ", "coffee_shop", ["congee"]),
    ("ร้านส้มตำขอนแก่น", "restaurant", ["isan"]),
    ("บ้านญาติ", "restaurant", []),
    ("ร้านริมคลองหมูกระทะสาขาในเมืองขอนแก่น", "fast_food_restaurant", ["hotpot_grill"]),
    ("ขนมจีนป้าแดง", "restaurant", ["noodle"]),
    ("Destiny Cafe", "coffee_shop", ["coffee"]),
    ("ครัวปู่ทอง", "restaurant", []),
    ("ร้านเจ๊ก้อย", "restaurant", []),
    ("ลาบก้อยอุบล", "restaurant", ["isan"]),
    ("ร้านอาหารตำบลด่าน", "restaurant", []),
    ("Tatsu Khao Yai", "japanese_restaurant", ["japanese"]),
    ("ครัวบ้านชิงช้า ส้มตำ ยำ อาหารตามสั่ง", "restaurant", ["isan", "rice_made_to_order"]),
])
def test_name_beats_taxonomy(name, tax, expected):
    assert tags_for(name, tax) == expected


def test_only_known_tags_come_out():
    assert set(tags_for("ซูชิ พิซซ่า ชานมไข่มุก ก๋วยเตี๋ยว ติ่มซำ", "restaurant")) <= set(TAGS)


@pytest.mark.parametrize("raw,clean", [
    ("ราดหน้าหม้อไฟซีฟู้ด : 0812345678", "ราดหน้าหม้อไฟซีฟู้ด"),
    ("ครัวป้า โทร. 081-234-5678", "ครัวป้า"),
    ("ครัวป้า tel 044 123 456 สาขา 2", "ครัวป้า สาขา 2"),
    ("ครัวป้า +66812345678", "ครัวป้า"),
    ("เมี่ยงปลาเผา 99 บาท", "เมี่ยงปลาเผา 99 บาท"),
    ("11.11 Gallery", "11.11 Gallery"),
    ("ร้าน\n  ส้มตำ ", "ร้าน ส้มตำ"),
    ("0812345678", ""),
    (r"ข้างวัด\n081 234 5678\nhttps://maps.app.goo.gl/x?y=1", "ข้างวัด"),
    ("อำเภอเมืองเลย โทร.0812345678", "อำเภอเมืองเลย"),
    ("15.2084250164116, 103.3201671951453", "15.2084250164116, 103.3201671951453"),
    ("ต 1000-1001 หมู่ 13","ต 1000-1001 หมู่ 13"),
    ("ศก.3061 5061 ตำบล ขะยูง", "ศก.3061 5061 ตำบล ขะยูง"),
])
def test_phone_numbers_are_removed(raw, clean):
    assert clean_text(raw) == clean


def test_slug_is_stable_readable_and_unique_per_source():
    a, b = slug_for("ร้าน ส้มตำ/1 <b>", "id-1"), slug_for("ร้าน ส้มตำ/1 <b>", "id-2")
    assert a.startswith("ร้าน-ส้มตำ-1-b-") and a != b and a == slug_for("ร้าน ส้มตำ/1 <b>", "id-1")
    assert not set(a) & set("/<>?#% ")
