"""Time parsing, formatting, and collision detection utilities."""

from datetime import datetime, time
from typing import Tuple


def parse_time_str(val: str) -> time:
    """Parses HH:MM or HH:MM:SS string to datetime.time."""
    parts = [int(p) for p in val.strip().split(":")]
    if len(parts) == 2:
        return time(hour=parts[0], minute=parts[1])
    elif len(parts) == 3:
        return time(hour=parts[0], minute=parts[1], second=parts[2])
    raise ValueError(f"Invalid time format: {val}")


def is_time_between(target: time, start: time, end: time) -> bool:
    """Returns True if target time is within [start, end]."""
    if start <= end:
        return start <= target <= end
    # Wrap around midnight
    return target >= start or target <= end


def slots_overlap(start_a: str, end_a: str, start_b: str, end_b: str) -> bool:
    """Checks whether two timetable time intervals overlap."""
    t_start_a = parse_time_str(start_a)
    t_end_a = parse_time_str(end_a)
    t_start_b = parse_time_str(start_b)
    t_end_b = parse_time_str(end_b)
    return max(t_start_a, t_start_b) < min(t_end_a, t_end_b)
