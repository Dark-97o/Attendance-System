"""Tests for entity identification in FaceEngine."""

import os
import tempfile
from database.db import init_db
from database.models import DatabaseManager
from engine.face_engine import FaceEngine


def test_is_teacher_id_check():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        init_db(db_path)
        db = DatabaseManager(db_path)
        db.register_teacher("T_PROF", "Prof. Xavier", "ECE")
        fe = FaceEngine(db=db)
        assert fe._is_teacher_id("T_PROF") is True
        assert fe._is_teacher_id("STUDENT_UNKNOWN") is False
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
