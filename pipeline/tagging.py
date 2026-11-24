"""Food tags, cleaned text and slugs derived from Thai restaurant names."""
import hashlib
import re

# Order matters only for output order; a name may match several tags.
_NAME_RULES = {
    "noodle": r"เตี๋ยว|ราดหน้า|บะหมี่|เย็นตาโฟ|ก๋วยจั๊บ|ขนมจีน|noodle",
    "isan": r"ส้มตำ|ส้มต่อน|ตำ[เแ]|ตำนัว|ตำปู|ลาบ|(?<!เจ๊)(?<!พี่)(?<!ป้า)(?<!แม่)(?<!น้อง)(?<!ครัว)ก้อย|แจ่ว|ไก่ย่าง|ปลาเผา|อีสาน",
    "hotpot_grill": r"หมูกระทะ|หมูกะทะ|ชาบู|shabu|สุกี้|suki\b|ปิ้งย่าง|เนื้อย่าง|บาร์บีคิว|\bbbq\b|จิ้มจุ่ม|หมูจุ่ม|ปลาจุ่ม",
    "coffee": r"กาแฟ|คอฟฟี่|coffee|คาเฟ่|caf[eé]\b|อเมซอน|amazon|espresso",
    "bakery_dessert": r"เบเกอ?รี่|bakery|เค้ก|\bcakes?\b|ขนม(?!จีน)|ไอศกรีม|ไอติม|ice ?cream|ปาท่องโก๋|dessert|บิงซู|นมสด",
    "rice_made_to_order": r"ตามสั่ง|ข้าวมันไก่|ข้าวแกง|ข้าวราดแกง|ข้าวขาหมู|ข้าวหมู|กะเพรา|กระเพรา",
    "congee": r"โจ๊ก|ข้าวต้ม",
    "seafood": r"ซีฟู้?ด|seafood|อาหารทะเล|กุ้งเผา|กุ้งสด|หอยทอด",
    "japanese": r"ซูชิ|sushi|ราเม[งน]|ramen|ญี่ปุ่น|japan|อิซากายะ|izakaya|ทาโกะยากิ",
    "korean": r"เกาหลี|korea|คิมบับ|ต๊อกบ",
    "vietnamese": r"เวียดนาม|vietnam|แหนมเนือง",
    "chinese": r"ติ่มซำ|dim ?sum|อาหารจีน|หม่าล่า|เสฉวน",
    "western": r"พิซซ่า|pizza|สเต[็๊]ก|steak|พาสต้า|pasta|เบอร์เกอร์|burger",
    "fast_food": r"\bkfc\b|เคเอฟซี|mcdonald|แมคโดนัลด์|ไก่ทอด",
    "bubble_tea": r"ชานม|ไข่มุก|bubble tea",
}
TAGS = tuple(_NAME_RULES)
_COMPILED = {tag: re.compile(rule, re.IGNORECASE) for tag, rule in _NAME_RULES.items()}

# Only taxonomy values that the gate sample did not show to be unreliable.
_TAXONOMY = {
    "ramen_restaurant": "noodle", "noodle_restaurant": "noodle",
    "coffee_shop": "coffee", "cafe": "coffee",
    "bakery": "bakery_dessert", "dessert_shop": "bakery_dessert", "ice_cream_shop": "bakery_dessert",
    "bubble_tea_shop": "bubble_tea", "japanese_restaurant": "japanese", "sushi_restaurant": "japanese",
    "korean_restaurant": "korean", "vietnamese_restaurant": "vietnamese", "chinese_restaurant": "chinese",
    "seafood_restaurant": "seafood", "steakhouse": "western", "pizza_restaurant": "western",
    "italian_restaurant": "western", "barbecue_restaurant": "hotpot_grill",
}

_PHONE = re.compile(
    r"(?:(?:โทรศัพท์|โทร|tel|phone)\s*\.?\s*[:：]?\s*(?:\+66|0)|[:：]?\s*(?:\+66|(?<![\d.])0))"
    r"[\s-]?\d(?:[\s-]?\d){6,8}(?!\d)", re.IGNORECASE)
_URL = re.compile(r"https?://\S+")


def tags_for(name: str, taxonomy: str) -> list[str]:
    tags = [tag for tag, rule in _COMPILED.items() if rule.search(name)]
    if not tags and taxonomy in _TAXONOMY:
        return [_TAXONOMY[taxonomy]]
    return tags


def clean_text(text: str) -> str:
    """Collapse whitespace and drop URLs and phone numbers (which may be an owner's personal number)."""
    text = _URL.sub(" ", text.replace(r"\n", " "))  # some addresses hold a literal backslash-n
    return re.sub(r"\s+", " ", _PHONE.sub(" ", text)).strip(" :：-|/,.")


def slug_for(name: str, source_id: str) -> str:
    readable = re.sub(r"[^0-9a-zก-๎]+", "-", name.lower()).strip("-")[:60].strip("-")
    return f"{readable or 'place'}-{hashlib.sha256(source_id.encode()).hexdigest()[:8]}"
