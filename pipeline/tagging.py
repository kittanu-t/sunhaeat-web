"""Food tags, cleaned text and slugs derived from Thai restaurant names."""
import hashlib
import re

from app.search.tags import TAGS, tags_in

__all__ = ["TAGS", "clean_text", "slug_for", "tags_for"]

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
    tags = tags_in(name)
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
