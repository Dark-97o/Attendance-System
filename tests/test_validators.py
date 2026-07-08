"""Unit tests for validator helpers."""

from backend.utils.validators import validate_identifier, validate_email, sanitize_string


def test_validate_identifier():
    assert validate_identifier("CSE6043") is True
    assert validate_identifier("ECE-1001") is True
    assert validate_identifier("t_01") is True
    assert validate_identifier("bad id with spaces") is False
    assert validate_identifier("") is False
    assert validate_identifier(None) is False


def test_validate_email():
    assert validate_email("user@college.edu") is True
    assert validate_email("john.doe@sub.domain.com") is True
    assert validate_email(None) is True
    assert validate_email("not-an-email") is False


def test_sanitize_string():
    assert sanitize_string("  hello world  ") == "hello world"
    assert sanitize_string(None, "default") == "default"
