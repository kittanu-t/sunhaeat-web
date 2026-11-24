import pytest

from app.search.normalize import normalize_name


@pytest.mark.parametrize("a,b", [
    ("ร้าน ส้ม ตำ", "ร้านส้มตำ"),
    ("Café", "cafe\u0301"),
    ("ส้มต\u0e4d\u0e32", "ส้มตำ"),
    ("KFC\u200b", "kfc"),
    ("\ufeffบ้าน\u00a0ญาติ", "บ้านญาติ"),
])
def test_equivalent_spellings(a, b):
    assert normalize_name(a) == normalize_name(b)


def test_different_tone_marks_stay_different():
    assert normalize_name("ข้าว") != normalize_name("ขาว")
