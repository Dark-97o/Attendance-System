"""Tests for fingerprint slot reassignment without collision."""

import os
import tempfile
from database.db import init_db
from database.models import DatabaseManager


def test_fingerprint_reassignment_releases_previous_owner():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        init_db(db_path)
        db = DatabaseManager(db_path)
        
        # Teacher 1 gets slot 5
        db.register_teacher("T1", "Teacher One", "CSE", fingerprint_id=5)
        t1 = db.get_teacher_by_id("T1")
        assert t1["fingerprint_id"] == 5

        # Teacher 2 gets slot 5 -> T1 should be released to NULL
        db.register_teacher("T2", "Teacher Two", "ECE", fingerprint_id=5)
        t2 = db.get_teacher_by_id("T2")
        t1_after = db.get_teacher_by_id("T1")
        
        assert t2["fingerprint_id"] == 5
        assert t1_after["fingerprint_id"] is None
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
