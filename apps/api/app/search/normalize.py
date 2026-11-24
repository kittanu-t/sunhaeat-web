import re
import unicodedata

# Whitespace plus zero-width characters that Thai input often carries between words.
_IGNORED = re.compile(r"[\s\u200b-\u200d\u2060\ufeff]+")


def normalize_name(s: str) -> str:
    """Key for comparing names: spelling-equivalent Thai/Latin strings map to the same value."""
    s = unicodedata.normalize("NFC", s).replace("\u0e4d\u0e32", "\u0e33")
    return _IGNORED.sub("", s.casefold())
