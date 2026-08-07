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
