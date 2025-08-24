from verify_matcha import _has_matcha_text


def test_direct_matcha_word():
    assert _has_matcha_text("Try our Matcha latte today!")


def test_secondary_keyword_without_matcha():
    text = "We serve ceremonial green tea desserts"
    assert _has_matcha_text(text)


def test_negative_word_only():
    assert not _has_matcha_text("Houjicha and sencha available")
