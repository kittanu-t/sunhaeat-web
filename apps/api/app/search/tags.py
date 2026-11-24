"""Food tags and the Thai words that signal them, shared by the dataset build and the query parser."""
import re

_RULES: dict[str, tuple[str, str]] = {
    "noodle": ("ก๋วยเตี๋ยว/เส้น", r"เตี๋ยว|ราดหน้า|บะหมี่|เย็นตาโฟ|ก๋วยจั๊บ|ขนมจีน|noodle"),
    "isan": ("อีสาน/ส้มตำ", r"ส้มตำ|ส้มต่อน|ตำ[เแ]|ตำนัว|ตำปู|ลาบ"
             r"|(?<!เจ๊)(?<!พี่)(?<!ป้า)(?<!แม่)(?<!น้อง)(?<!ครัว)ก้อย|แจ่ว|ไก่ย่าง|ปลาเผา|อีสาน"),
    "hotpot_grill": ("หมูกระทะ/ชาบู", r"หมูกระทะ|หมูกะทะ|ชาบู|shabu|สุกี้|suki\b|ปิ้งย่าง|เนื้อย่าง|บาร์บีคิว|\bbbq\b"
                     r"|จิ้มจุ่ม|หมูจุ่ม|ปลาจุ่ม"),
    "coffee": ("กาแฟ/คาเฟ่", r"กาแฟ|คอฟฟี่|coffee|คาเฟ่|caf[eé]\b|อเมซอน|amazon|espresso"),
    "bakery_dessert": ("เบเกอรี่/ของหวาน", r"เบเกอ?รี่|bakery|เค้ก|\bcakes?\b|ขนม(?!จีน)|ไอศกรีม|ไอติม|ice ?cream"
                       r"|ปาท่องโก๋|dessert|บิงซู|นมสด|ของหวาน"),
    "rice_made_to_order": ("ข้าว/ตามสั่ง", r"ตามสั่ง|ข้าวมันไก่|ข้าวแกง|ข้าวราดแกง|ข้าวขาหมู|ข้าวหมู|กะเพรา|กระเพรา"),
    "congee": ("โจ๊ก/ข้าวต้ม", r"โจ๊ก|ข้าวต้ม"),
    "seafood": ("อาหารทะเล", r"ซีฟู้?ด|seafood|อาหารทะเล|กุ้งเผา|กุ้งสด|หอยทอด"),
    "japanese": ("ญี่ปุ่น", r"ซูชิ|sushi|ราเม[งน]|ramen|ญี่ปุ่น|japan|อิซากายะ|izakaya|ทาโกะยากิ"),
    "korean": ("เกาหลี", r"เกาหลี|korea|คิมบับ|ต๊อกบ"),
    "vietnamese": ("เวียดนาม", r"เวียดนาม|vietnam|แหนมเนือง"),
    "chinese": ("จีน", r"ติ่มซำ|dim ?sum|อาหารจีน|หม่าล่า|เสฉวน"),
    "western": ("ตะวันตก/สเต๊ก", r"พิซซ่า|pizza|สเต[็๊]ก|steak|พาสต้า|pasta|เบอร์เกอร์|burger"),
    "fast_food": ("ฟาสต์ฟู้ด/ไก่ทอด", r"\bkfc\b|เคเอฟซี|mcdonald|แมคโดนัลด์|ไก่ทอด|ฟาสต์?ฟู้ด"),
    "bubble_tea": ("ชานม", r"ชานม|ไข่มุก|bubble tea"),
}
TAGS = tuple(_RULES)
LABELS = {tag: label for tag, (label, _) in _RULES.items()}
_COMPILED = {tag: re.compile(rule, re.IGNORECASE) for tag, (_, rule) in _RULES.items()}


def tags_in(text: str) -> list[str]:
    return [tag for tag, rule in _COMPILED.items() if rule.search(text)]
