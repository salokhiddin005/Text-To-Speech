from tts.normalize import normalize_text


def test_abbreviations():
    assert "Doctor" in normalize_text("Hello Dr. Smith")
    assert "Mister" in normalize_text("Mr. Smith arrived")
    assert "Saint" in normalize_text("St. Patrick")


def test_numbers_to_words():
    assert "five" in normalize_text("I have 5 apples")
    assert "one hundred" in normalize_text("Page 100 of the book")


def test_ordinals():
    assert "third" in normalize_text("The 3rd day")
    assert "twenty-first" in normalize_text("The 21st of June")
    assert "first" in normalize_text("on the 1st")


def test_symbols_expanded():
    assert "percent" in normalize_text("50% off")
    assert " and " in normalize_text("salt & pepper")
    assert "dollar" in normalize_text("100$")


def test_currency_reads_in_spoken_order():
    # Written "$100", spoken "one hundred dollars" — not "dollar one hundred".
    assert normalize_text("$100") == "one hundred dollars"
    assert normalize_text("€50") == "fifty euros"
    assert normalize_text("£20") == "twenty pounds"


def test_currency_singular():
    assert normalize_text("$1") == "one dollar"


def test_whitespace_collapsed():
    assert normalize_text("hello   world") == "hello world"
    assert normalize_text("  hello  ").strip() == "hello"


def test_passthrough_simple():
    assert normalize_text("Hello world") == "Hello world"


def test_empty_string_safe():
    assert normalize_text("") == ""


def test_language_for_voice_covers_every_configured_voice():
    from tts.engine import VOICES
    from tts.normalize import SYMBOLS, language_for_voice

    for voice_id in VOICES:
        lang = language_for_voice(voice_id)
        assert lang in SYMBOLS, f"{voice_id} maps to unsupported language {lang!r}"


def test_numbers_use_the_voices_own_language():
    # The whole point: a Spanish voice handed "twenty-five" pronounces English
    # letters with Spanish phonetics, which is unintelligible.
    assert "veinticinco" in normalize_text("Tengo 25 años", "es")
    assert "vingt-cinq" in normalize_text("J'ai 25 ans", "fr")
    assert "fünfundzwanzig" in normalize_text("Ich habe 25 Bucher", "de")
    assert "venticinque" in normalize_text("Ho 25 anni", "it")
    assert "vinte e cinco" in normalize_text("Tenho 25 anos", "pt_BR")
    assert "двадцать пять" in normalize_text("У меня 25 книг", "ru")


def test_no_english_leaks_into_other_languages():
    # Only markers no other language legitimately shares: French and German
    # really do say "plus", and several say "dollar", so those prove nothing.
    for lang in ("es", "fr", "de", "it", "pt_BR", "ru", "ar"):
        out = normalize_text("25 + 100% = $50", lang)
        for english in ("twenty-five", "percent", "equals", "fifty"):
            assert english not in out, f"{english!r} leaked into {lang}: {out}"


def test_symbols_are_localised():
    assert "por ciento" in normalize_text("50%", "es")
    assert "pour cent" in normalize_text("50%", "fr")
    assert "Prozent" in normalize_text("50%", "de")
    assert "процентов" in normalize_text("50%", "ru")


def test_currency_both_orders_and_leftovers():
    assert normalize_text("100$", "en") == "one hundred dollars"
    assert normalize_text("$100", "en") == "one hundred dollars"
    assert "dólares" in normalize_text("100$", "es")
    # A glyph with no amount still has to be spoken, not left as a symbol.
    assert "$" not in normalize_text("a $ sign", "en")


def test_english_only_rules_do_not_fire_elsewhere():
    # "St." is a Spanish word fragment as often as an abbreviation; only English
    # text should get title expansion or English ordinal handling.
    assert "Doctor" not in normalize_text("Dr. Smith", "es")
    assert "third" not in normalize_text("3rd", "es")


def test_unknown_language_falls_back_without_crashing():
    assert normalize_text("I have 5 books", "xx")
