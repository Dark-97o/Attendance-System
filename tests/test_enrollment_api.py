"""Validation test cases for enrollment payloads."""

import pytest
from pydantic import ValidationError
from backend.schemas import StudentEnrollRequest, TeacherEnrollRequest


def test_valid_student_enroll_payload():
    payload = StudentEnrollRequest(
        student_id="CSE6043",
        name="John Student",
        class_section="CSE-6A",
        roll_number="43"
    )
    assert payload.student_id == "CSE6043"
    assert payload.name == "John Student"


def test_invalid_student_enroll_short_id():
    with pytest.raises(ValidationError):
        StudentEnrollRequest(
            student_id="x",
            name="Valid Name",
            class_section="CSE"
        )
