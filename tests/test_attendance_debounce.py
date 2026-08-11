"""Tests for attendance mark debouncing."""

import time
from backend.routes.attendance import is_attendance_debounced, _STUDENT_LAST_LOG


def test_attendance_debouncing():
    _STUDENT_LAST_LOG.clear()
    assert is_attendance_debounced("S1", cooldown_seconds=10) is False
    # Immediately check again -> should be debounced
    assert is_attendance_debounced("S1", cooldown_seconds=10) is True
