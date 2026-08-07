"""Text normalization: expand abbreviations, symbols, and numbers."""

import re

from num2words import num2words

ABBREVIATIONS = {
    r"\bMr\.": "Mister",
    r"\bMrs\.": "Missus",
    r"\bMs\.": "Miss",
    r"\bDr\.": "Doctor",
    r"\bSt\.": "Saint",
    r"\bJr\.": "Junior",
    r"\bSr\.": "Senior",
    r"\bvs\.": "versus",
    r"\betc\.": "et cetera",
    r"\bi\.e\.": "that is",
    r"\be\.g\.": "for example",
}

SYMBOLS = {
    "&": " and ",
    "@": " at ",
    "%": " percent ",
    "$": " dollar ",
    "€": " euro ",
    "£": " pound ",
    "#": " number ",
    "+": " plus ",
    "=": " equals ",
}

# Currency symbols precede the amount in writing but follow it in speech, so
# "$100" has to become "100 dollars" before the generic symbol pass turns it
# into the backwards "dollar 100".
CURRENCY_UNITS = {"$": ("dollar", "dollars"), "€": ("euro", "euros"), "£": ("pound", "pounds")}
CURRENCY_RE = re.compile(r"([$€£])\s?(\d+(?:\.\d+)?)")

ORDINAL_RE = re.compile(r"\b(\d+)(?:st|nd|rd|th)\b", re.IGNORECASE)
NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
WHITESPACE_RE = re.compile(r"\s+")


def _currency_to_words(match: re.Match) -> str:
    symbol, amount = match.group(1), match.group(2)
    singular, plural = CURRENCY_UNITS[symbol]
    unit = singular if float(amount) == 1 else plural
    return f"{amount} {unit}"


def _ordinal_to_words(match: re.Match) -> str:
    try:
        return num2words(int(match.group(1)), to="ordinal")
    except (ValueError, OverflowError):
        return match.group(0)


def _number_to_words(match: re.Match) -> str:
    num_str = match.group(0)
    try:
        value = float(num_str) if "." in num_str else int(num_str)
        return num2words(value)
    except (ValueError, OverflowError):
        return num_str


def normalize_text(text: str) -> str:
    """Expand abbreviations, symbols, and numbers into spoken form."""
    for pattern, replacement in ABBREVIATIONS.items():
        text = re.sub(pattern, replacement, text)
    text = CURRENCY_RE.sub(_currency_to_words, text)
    for symbol, replacement in SYMBOLS.items():
        text = text.replace(symbol, replacement)
    text = ORDINAL_RE.sub(_ordinal_to_words, text)
    text = NUMBER_RE.sub(_number_to_words, text)
    text = WHITESPACE_RE.sub(" ", text).strip()
    return text
