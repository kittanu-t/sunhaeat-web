import re
import unicodedata

# Whitespace plus zero-width characters that Thai input often carries between words.
_IGNORED = re.compile(r"[\s\u200b-\u200d\u2060\ufeff]+")
_TONE = "\u0e48-\u0e4b"


def canonical_thai(s: str) -> str:
    """One spelling for Thai sequences that look the same on screen."""
    s = unicodedata.normalize("NFC", s).replace("\u0e40\u0e40", "\u0e41")  # two SARA E typed for SARA AE
    s = re.sub(f"\u0e4d([{_TONE}]?)\u0e32", "\\1\u0e33", s)  # nikhahit, optional tone, SARA AA
    s = s.replace("\u0e4d\u0e32", "\u0e33")
    return re.sub(f"\u0e33([{_TONE}])", "\\1\u0e33", s)  # tone typed after SARA AM


def normalize_name(s: str) -> str:
    """Key for comparing names: spelling-equivalent Thai/Latin strings map to the same value."""
    return _IGNORED.sub("", canonical_thai(s).casefold())
