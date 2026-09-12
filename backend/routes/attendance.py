"""
Attendance Records and Analytics API routes.
Provides live session logs, historical records, trend analysis, and CSV export.
"""

import io
import csv
from fastapi import APIRouter, Response, HTTPException, Query
from typing import Optional, Dict, Any

router = APIRouter(prefix="/api/attendance", tags=["Attendance"])

_context: Dict[str, Any] = {}

def set_router_context(app_context: Dict[str, Any]):
    global _context
    _context = app_context

def get_context():
    return _context

@router.get("/live")
def get_live_attendance():
    """Returns attendance records for the currently active lecture session."""
    ctx = get_context()
    att_mgr = ctx["attendance_manager"]
    db = ctx["db"]
    
    if not att_mgr.active_session:
        return {
            "session_active": False,
            "session": None,
            "records": [],
            "count": 0
        }
    
    session_id = att_mgr.active_session["id"]
    records = db.get_session_attendance(session_id)
    return {
        "session_active": True,
        "session": att_mgr.active_session,
        "records": records,
        "count": len(records)
    }

@router.get("/analytics")
def get_attendance_analytics():
    """Provides daily, weekly, and monthly trends for Chart.js dashboard widgets."""
    ctx = get_context()
    db = ctx["db"]
    att_mgr = ctx["attendance_manager"]
    
    analytics = db.get_attendance_analytics()
    
    # Calculate live session attendance rate if active
    present_now = 0
    if att_mgr.active_session:
        records = db.get_session_attendance(att_mgr.active_session["id"])
        present_now = len(records)
        
    total_enrolled = max(analytics["total_enrolled"], 1)
    rate = round((present_now / total_enrolled) * 100, 1)

    analytics["current_present"] = present_now
    analytics["attendance_percentage"] = rate
    analytics["session_active"] = att_mgr.active_session is not None
    return analytics

@router.get("/records")
def get_historical_records(session_id: Optional[int] = None):
    ctx = get_context()
    db = ctx["db"]
    
    if session_id is not None:
        records = db.get_session_attendance(session_id)
    else:
        # Get all records across sessions
        with db._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ar.*, s.name as student_name, s.roll_number, s.class_section, 
                       ls.course_code, ls.course_name, ls.start_time as session_start
                FROM attendance_records ar
                JOIN students s ON ar.student_id = s.student_id
                JOIN lecture_sessions ls ON ar.session_id = ls.id
                ORDER BY ar.entry_time DESC
                LIMIT 100
            """)
            records = [dict(r) for r in cursor.fetchall()]
            
    return {"records": records, "count": len(records)}

@router.get("/export/csv")
def export_attendance_csv(session_id: Optional[int] = None):
    """Generates an academic attendance report formatted as downloadable CSV."""
    ctx = get_context()
    db = ctx["db"]

    with db._get_conn() as conn:
        cursor = conn.cursor()
        query = """
            SELECT ar.id, ls.session_code, ls.course_code, ls.course_name, t.name as teacher_name,
                   s.student_id, s.name as student_name, s.roll_number, s.class_section,
                   ar.entry_time, ar.exit_time, ar.confidence, ar.status
            FROM attendance_records ar
            JOIN students s ON ar.student_id = s.student_id
            JOIN lecture_sessions ls ON ar.session_id = ls.id
            JOIN teachers t ON ls.teacher_id = t.teacher_id
        """
        params = ()
        if session_id is not None:
            query += " WHERE ar.session_id = ?"
            params = (session_id,)
        query += " ORDER BY ar.entry_time DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Record ID", "Session Code", "Course Code", "Course Name", "Teacher",
        "Student ID", "Student Name", "Roll Number", "Section",
        "Entry Time", "Exit / Last Seen", "Match Confidence", "Status"
    ])

    for r in rows:
        writer.writerow([
            r["id"], r["session_code"], r["course_code"], r["course_name"], r["teacher_name"],
            r["student_id"], r["student_name"], r["roll_number"], r["class_section"],
            r["entry_time"], r["exit_time"], f"{r['confidence']:.2f}", r["status"]
        ])

    csv_data = output.getvalue()
    filename = f"attendance_report_{session_id or 'all'}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
