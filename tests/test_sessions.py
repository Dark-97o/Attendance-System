"""Tests for lecture session duration calculation."""

from backend.routes.sessions import calculate_session_duration_minutes


def test_calculate_session_duration_minutes():
    s1 = "2026-08-11 10:00:00"
    s2 = "2026-08-11 10:45:00"
    dur = calculate_session_duration_minutes(s1, s2)
    assert dur == 45.0
