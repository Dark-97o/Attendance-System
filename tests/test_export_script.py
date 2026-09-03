"""Tests for attendance export query builder."""

import os
import tempfile
from database.db import init_db
from database.models import DatabaseManager
from scripts.export_attendance import fetch_attendance


def test_fetch_attendance_empty():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        init_db(db_path)
        records = fetch_attendance(db_path)
        assert len(records) == 0
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
