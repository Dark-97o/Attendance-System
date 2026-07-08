"""Unit tests for time utilities and slot overlap logic."""

import pytest
from datetime import time
from backend.utils.time_utils import parse_time_str, is_time_between, slots_overlap


def test_parse_time_str():
    t = parse_time_str("09:30")
    assert t == time(9, 30)
    t2 = parse_time_str("14:45:10")
    assert t2 == time(14, 45, 10)


def test_is_time_between():
    assert is_time_between(time(10, 0), time(9, 0), time(11, 0))
    assert not is_time_between(time(8, 59), time(9, 0), time(11, 0))
    assert is_time_between(time(23, 30), time(22, 0), time(1, 0))


def test_slots_overlap():
    assert slots_overlap("09:00", "10:00", "09:30", "10:30")
    assert not slots_overlap("09:00", "10:00", "10:00", "11:00")
    assert not slots_overlap("11:00", "12:00", "09:00", "10:00")
