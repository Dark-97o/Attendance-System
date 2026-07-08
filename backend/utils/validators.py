"""Input sanitization and validation helpers."""

import re
from typing import Optional


EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
ID_REGEX = re.compile(r"^[A-Za-z0-9_-]{2,32}$")


def validate_identifier(val: Optional[str]) -> bool:
    """Validates alphanumeric entity identifiers (student_id, teacher_id)."""
    if not val:
        return False
    return bool(ID_REGEX.match(val.strip()))


def validate_email(email: Optional[str]) -> bool:
    """Checks whether an email address format is valid."""
    if not email:
        return True  # Email is optional in most schemas
    return bool(EMAIL_REGEX.match(email.strip()))


def sanitize_string(val: Optional[str], default: str = "") -> str:
    """Strips leading/trailing whitespace and normalizes text."""
    if val is None:
        return default
    return val.strip()
