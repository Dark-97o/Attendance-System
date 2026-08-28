"""Tests for cascading teacher deletion and timetable routine cleanup."""

import os
import tempfile
from database.db import init_db
from database.models import DatabaseManager


def test_teacher_deletion_cascade():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        init_db(db_path)
        db = DatabaseManager(db_path)
        db.register_teacher("T_DEL", "Temporary Teacher", "CSE", fingerprint_id=9)
        db.add_teacher_face_embedding("T_DEL", [0.5] * 128)
        
        db.delete_teacher("T_DEL")
        assert db.get_teacher_by_id("T_DEL") is None
        
        # Verify face embedding was removed
        faces = [f for f in db.get_all_enrolled_faces() if f["student_id"] == "T_DEL"]
        assert len(faces) == 0
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
