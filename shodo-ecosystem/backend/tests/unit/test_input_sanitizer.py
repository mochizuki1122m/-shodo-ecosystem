import pytest

from src.core.security import InputSanitizer


def test_sanitize_string_keeps_japanese_characters():
    text = "日本語のテキストとEmoji😊を含む入力\n改行と\tタブも許可"
    cleaned = InputSanitizer.sanitize_string(text, max_length=100)
    assert "日本語" in cleaned
    assert "Emoji" in cleaned
    assert "\n" in cleaned
    assert "\t" in cleaned


def test_sanitize_string_removes_control_chars_and_truncates():
    text = "Hello\x00World\x01\x02\x03" + "A" * 200
    cleaned = InputSanitizer.sanitize_string(text, max_length=50)
    assert "\x00" not in cleaned
    assert len(cleaned) <= 50