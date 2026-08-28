"""Unit tests for teacher biometric face vector operations."""

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


def test_add_and_retrieve_teacher_face_embedding(temp_db):
    temp_db.register_teacher("T_1001", "Dr. Alan", "CSE", fingerprint_id=1)
    fake_vector = [0.1] * 128
    ok = temp_db.add_teacher_face_embedding("T_1001", fake_vector)
    assert ok is True

    faces = temp_db.get_all_enrolled_faces()
    matching = [f for f in faces if f["student_id"] == "T_1001"]
    assert len(matching) == 1
    assert matching[0]["name"] == "Dr. Alan"
    assert matching[0]["embedding"] == fake_vector
