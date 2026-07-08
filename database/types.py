"""Typed structures and TypedDicts for database records."""

from typing import TypedDict, Optional, List, Dict, Any


class StudentRecord(TypedDict):
    student_id: str
    name: str
    roll_number: Optional[str]
    email: Optional[str]
    class_section: str
    photo_path: Optional[str]
    created_at: str


class TeacherRecord(TypedDict):
    teacher_id: str
    name: str
    department: str
    fingerprint_id: Optional[int]
    photo_path: Optional[str]
    created_at: str


class AttendanceLog(TypedDict):
    id: int
    student_id: str
    session_id: Optional[int]
    status: str
    method: str
    confidence: Optional[float]
    timestamp: str
