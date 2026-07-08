"""Tests for Student CRUD operations in DatabaseManager."""

import os
import tempfile
import pytest
from database.db import init_db
from database.models import DatabaseManager


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    init_db(db_path)
    db = DatabaseManager(db_path)
    yield db
    if os.path.exists(db_path):
        os.remove(db_path)


def test_register_and_get_student(temp_db):
    ok = temp_db.register_student("STU_101", "Alice Smith", "101", "CSE-A", "test@test.com")
    assert ok is True

    student = temp_db.get_student_by_id("STU_101")
    assert student is not None
    assert student["name"] == "Alice Smith"
    assert student["class_section"] == "CSE-A"


def test_list_students_filtering(temp_db):
    temp_db.register_student("S1", "Alice", "1", "CSE", "a@test.com")
    temp_db.register_student("S2", "Bob", "2", "ECE", "b@test.com")
    
    all_students = temp_db.list_students()
    assert len(all_students) == 2
