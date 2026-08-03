"""Pydantic schemas for API request and response validation."""

from pydantic import BaseModel, Field
from typing import Optional, List


class StudentEnrollRequest(BaseModel):
    student_id: str = Field(..., min_length=2, max_length=32)
    name: str = Field(..., min_length=2, max_length=100)
    class_section: str = Field(..., min_length=1, max_length=32)
    roll_number: Optional[str] = None
    email: Optional[str] = None


class TeacherEnrollRequest(BaseModel):
    teacher_id: str = Field(..., min_length=2, max_length=32)
    name: str = Field(..., min_length=2, max_length=100)
    department: str = Field(default="CSE", max_length=32)
    fingerprint_id: Optional[int] = None


class SessionAuthRequest(BaseModel):
    fingerprint_id: int
    room_id: Optional[str] = "LAB-1"
