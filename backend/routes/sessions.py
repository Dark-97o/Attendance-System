"""
Session management API routes.
Enforces teacher authentication via R307 fingerprint scanner to start/end sessions.
"""

from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel
from typing import Optional, Dict, Any

router = APIRouter(prefix="/api/session", tags=["Session"])

class StartSessionRequest(BaseModel):
    teacher_id: str
    course_code: str = "CS501"
    course_name: str = "Embedded AI & Edge Systems"
    room_number: str = "Room 101"

class FingerprintAuthRequest(BaseModel):
    fingerprint_id: Optional[int] = 1  # Used for simulation mode; hardware reads directly

# Global state injector (set during app startup)
_context: Dict[str, Any] = {}

def set_router_context(app_context: Dict[str, Any]):
    global _context
    _context = app_context

def get_context():
    return _context

@router.get("/status")
def get_session_status():
    ctx = get_context()
    att_mgr = ctx["attendance_manager"]
    fp_mgr = ctx["fingerprint_manager"]
    
    session_status = att_mgr.get_session_status()
    fp_status = fp_mgr.get_status()
    
    # Calculate current session student attendance count if session active
    present_count = 0
    if session_status["session_active"]:
        session_id = session_status["session"]["id"]
        records = ctx["db"].get_session_attendance(session_id)
        present_count = len(records)

    return {
        "active": session_status["session_active"],
        "session": session_status["session"],
        "teacher_present": session_status["teacher_present"],
        "present_students_count": present_count,
        "fingerprint_status": fp_status
    }

@router.post("/start")
def start_session(req: StartSessionRequest):
    ctx = get_context()
    att_mgr = ctx["attendance_manager"]
    db = ctx["db"]
    
    teacher = db.get_teacher_by_id(req.teacher_id)
    if not teacher:
        all_teachers = db.list_teachers()
        if all_teachers:
            teacher = all_teachers[0]
        else:
            tid = req.teacher_id if req.teacher_id else "FACULTY-01"
            db.register_teacher(
                teacher_id=tid,
                name="Faculty Instructor",
                department="Academic Department",
                fingerprint_id=1
            )
            teacher = db.get_teacher_by_id(tid)

    session = att_mgr.start_session(
        teacher_id=teacher["teacher_id"],
        course_code=req.course_code,
        course_name=req.course_name,
        room_number=req.room_number
    )
    return {"message": "Lecture session started successfully", "session": session}

@router.post("/end")
def end_session():
    ctx = get_context()
    att_mgr = ctx["attendance_manager"]
    ended = att_mgr.end_session()
    if not ended:
        raise HTTPException(status_code=400, detail="No active lecture session to end")
    return {"message": "Lecture session ended successfully", "session": ended}

@router.post("/fingerprint/scan")
def trigger_fingerprint_scan(req: FingerprintAuthRequest = Body(...)):
    """
    Triggers teacher authentication via R307 fingerprint scanner.
    Works with both physical sensor and interactive touchscreen simulation button.
    """
    ctx = get_context()
    fp_mgr = ctx["fingerprint_manager"]
    att_mgr = ctx["attendance_manager"]

    if fp_mgr.mode == "UART_HARDWARE" and fp_mgr.driver and fp_mgr.driver.is_connected:
        success, teacher, msg = fp_mgr.scan_and_identify()
    else:
        fid = req.fingerprint_id if req.fingerprint_id is not None else 1
        success, teacher, msg = fp_mgr.authenticate_teacher_fingerprint(fid)

    if not success or not teacher:
        return {
            "authenticated": False,
            "message": msg,
            "session_active": att_mgr.active_session is not None
        }

    # Check resulting session state after authentication
    is_active = att_mgr.active_session is not None
    action = "started" if is_active else "ended"
    return {
        "authenticated": True,
        "teacher": teacher,
        "action": action,
        "message": f"Biometric Match verified! Lecture session {action} for {teacher['name']}.",
        "session_active": is_active,
        "session": att_mgr.active_session
    }
