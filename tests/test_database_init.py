"""Unit test for database schema initialization."""

import os
import sqlite3
import tempfile
import pytest
from database.db import init_db


def test_database_init_creates_tables():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        expected = {"students", "teachers", "face_embeddings", "lecture_sessions", "attendance_records", "timetable_routines"}
        for tbl in expected:
            assert tbl in tables, f"Expected table {tbl} was not created"
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
