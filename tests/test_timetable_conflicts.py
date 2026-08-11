"""Tests for timetable slot collision detection."""

from backend.routes.timetable import check_timetable_conflict


def test_timetable_no_conflict():
    existing = [
        {"id": 1, "day_of_week": "Monday", "start_time": "09:00", "end_time": "10:00", "subject": "Math"}
    ]
    has_conflict, _ = check_timetable_conflict(existing, "Monday", "10:30", "11:30")
    assert has_conflict is False


def test_timetable_overlap_conflict():
    existing = [
        {"id": 1, "day_of_week": "Monday", "start_time": "09:00", "end_time": "10:00", "subject": "Math"}
    ]
    has_conflict, msg = check_timetable_conflict(existing, "Monday", "09:30", "10:30")
    assert has_conflict is True
    assert "Conflict with Math" in msg
