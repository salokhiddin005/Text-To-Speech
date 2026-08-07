"""Text normalization: expand abbreviations, symbols, and numbers.

Everything here is language-aware. Expanding "25" to "twenty-five" for a
Spanish voice does not merely sound wrong — the voice pronounces the English
letters with Spanish phonetics, which is unintelligible. So the caller passes
the language of the voice doing the speaking, and each table is keyed by it.
"""

import re

from num2words import num2words

DEFAULT_LANG = "en"

# Voice ids look like "es_ES-davefx-medium"; num2words wants a language code.
_LOCALE_OVERRIDES = {"pt_BR": "pt_BR"}


def language_for_voice(voice_id: str) -> str:
    """Map a voice id to the language code used by the tables below."""
    locale = voice_id.split("-", 1)[0]
    if locale in _LOCALE_OVERRIDES:
        return _LOCALE_OVERRIDES[locale]
    return locale.split("_", 1)[0] or DEFAULT_LANG


# Titles are English conventions, so they are only expanded for English text.
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
    "en": {"&": "and", "@": "at", "%": "percent", "#": "number", "+": "plus", "=": "equals"},
    "es": {"&": "y", "@": "arroba", "%": "por ciento", "#": "número", "+": "más", "=": "igual"},
    "fr": {"&": "et", "@": "arobase", "%": "pour cent", "#": "numéro", "+": "plus", "=": "égale"},
    "de": {"&": "und", "@": "at", "%": "Prozent", "#": "Nummer", "+": "plus", "=": "gleich"},
    "it": {"&": "e", "@": "chiocciola", "%": "per cento", "#": "numero", "+": "più", "=": "uguale"},
    "pt_BR": {"&": "e", "@": "arroba", "%": "por cento", "#": "número", "+": "mais", "=": "igual"},
    "ru": {"&": "и", "@": "собака", "%": "процентов", "#": "номер", "+": "плюс", "=": "равно"},
    "ar": {"&": "و", "@": "آت", "%": "بالمئة", "#": "رقم", "+": "زائد", "=": "يساوي"},
}

# (singular, plural). Languages with richer plural rules than two forms — Russian
# among them — are approximated; it stays far closer than reading English would.
CURRENCIES = {
    "en": {"$": ("dollar", "dollars"), "€": ("euro", "euros"), "£": ("pound", "pounds")},
    "es": {"$": ("dólar", "dólares"), "€": ("euro", "euros"), "£": ("libra", "libras")},
    "fr": {"$": ("dollar", "dollars"), "€": ("euro", "euros"), "£": ("livre", "livres")},
    "de": {"$": ("Dollar", "Dollar"), "€": ("Euro", "Euro"), "£": ("Pfund", "Pfund")},
    "it": {"$": ("dollaro", "dollari"), "€": ("euro", "euro"), "£": ("sterlina", "sterline")},
    "pt_BR": {"$": ("dólar", "dólares"), "€": ("euro", "euros"), "£": ("libra", "libras")},
    "ru": {"$": ("доллар", "долларов"), "€": ("евро", "евро"), "£": ("фунт", "фунтов")},
    "ar": {"$": ("دولار", "دولار"), "€": ("يورو", "يورو"), "£": ("جنيه", "جنيه")},
}

# "3rd" is an English spelling; other languages mark ordinals differently, so
# this pattern is only applied to English text.
ORDINAL_RE = re.compile(r"\b(\d+)(?:st|nd|rd|th)\b", re.IGNORECASE)
NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
# Both orders occur in the wild ("$100" and "100$"), and either way the unit is
# spoken after the amount.
CURRENCY_PREFIX_RE = re.compile(r"([$€£])\s?(\d+(?:\.\d+)?)")
CURRENCY_SUFFIX_RE = re.compile(r"(\d+(?:\.\d+)?)\s?([$€£])")
WHITESPACE_RE = re.compile(r"\s+")


def _table(mapping: dict, lang: str) -> dict:
    return mapping.get(lang, mapping[DEFAULT_LANG])


def _to_words(value, lang: str, **kwargs) -> str:
    try:
        return num2words(value, lang=lang, **kwargs)
    except (NotImplementedError, TypeError, ValueError, OverflowError):
        # Unknown language for num2words: English is a poor result but a silent
        # crash mid-sentence is worse.
        return num2words(value, **kwargs)


def normalize_text(text: str, lang: str = DEFAULT_LANG) -> str:
    """Expand abbreviations, symbols, and numbers into spoken form.

    `lang` should come from `language_for_voice()` for the voice being used.
    """
    if lang == "en":
        for pattern, replacement in ABBREVIATIONS.items():
            text = re.sub(pattern, replacement, text)

    # Currency symbols precede the amount in writing but follow it in speech,
    # so this has to run before the generic symbol pass.
    currencies = _table(CURRENCIES, lang)

    def spoken_amount(amount: str, symbol: str) -> str:
        singular, plural = currencies[symbol]
        return f"{amount} {singular if float(amount) == 1 else plural}"

    text = CURRENCY_PREFIX_RE.sub(lambda m: spoken_amount(m.group(2), m.group(1)), text)
    text = CURRENCY_SUFFIX_RE.sub(lambda m: spoken_amount(m.group(1), m.group(2)), text)

    for symbol, word in _table(SYMBOLS, lang).items():
        text = text.replace(symbol, f" {word} ")

    # Any currency glyph left over had no amount attached to it; say its name
    # rather than leaving a symbol the voice cannot pronounce.
    for symbol, (singular, _plural) in currencies.items():
        text = text.replace(symbol, f" {singular} ")

    if lang == "en":
        text = ORDINAL_RE.sub(
            lambda m: _to_words(int(m.group(1)), lang, to="ordinal"),
            text,
        )

    def number_to_words(match: re.Match) -> str:
        raw = match.group(0)
        try:
            value = float(raw) if "." in raw else int(raw)
        except ValueError:
            return raw
        return _to_words(value, lang)

    text = NUMBER_RE.sub(number_to_words, text)
    return WHITESPACE_RE.sub(" ", text).strip()
