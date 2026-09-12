"""
Timetable and Routine management router.
Provides endpoints for scheduling, timetable CSV/JSON upload, and real-time teacher presence alerts.
"""

import csv
import io
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel, Field

from database.models import DatabaseManager

logger = logging.getLogger("attendance.timetable")
router = APIRouter(prefix="/api/timetable", tags=["timetable"])

def get_db():
    return DatabaseManager()

class RoutineCreateRequest(BaseModel):
    class_name: str = Field(..., description="Target class section, e.g. CSE A")
    day_of_week: str = Field(..., description="Day name, e.g. Monday")
    start_time: str = Field(..., description="Start time in HH:MM format, e.g. 09:00")
    end_time: str = Field(..., description="End time in HH:MM format, e.g. 10:00")
    subject: str = Field(..., description="Course subject or lecture title")
    teacher_id: Optional[str] = Field(None, description="Assigned faculty ID")
    teacher_name: Optional[str] = Field(None, description="Assigned faculty name")
    room_number: Optional[str] = Field("Room 101", description="Lecture hall or lab")

@router.get("/routines")
async def get_routines(
    class_name: Optional[str] = None,
    day_of_week: Optional[str] = None,
    db: DatabaseManager = Depends(get_db)
):
    """Retrieve all timetable routine entries, optionally filtered by class or day."""
    routines = db.list_timetable_routines(class_name=class_name, day_of_week=day_of_week)
    return {"success": True, "count": len(routines), "routines": routines}

@router.post("/routine")
async def create_routine(
    req: RoutineCreateRequest,
    db: DatabaseManager = Depends(get_db)
):
    """Add a new lecture period to the timetable routine."""
    # Look up teacher name if not provided
    teacher_name = req.teacher_name
    if req.teacher_id and not teacher_name:
        teacher = db.get_teacher_by_id(req.teacher_id)
        if teacher:
            teacher_name = teacher.get("name")

    routine_id = db.add_timetable_routine(
        class_name=req.class_name,
        day_of_week=req.day_of_week,
        start_time=req.start_time,
        end_time=req.end_time,
        subject=req.subject,
        teacher_id=req.teacher_id,
        teacher_name=teacher_name,
        room_number=req.room_number or "Room 101"
    )
    return {"success": True, "routine_id": routine_id, "message": "Routine created successfully"}

@router.post("/upload")
async def upload_routine_file(
    file: UploadFile = File(...),
    db: DatabaseManager = Depends(get_db)
):
    """
    Upload and parse a timetable schedule file (CSV or JSON).
    CSV Format expected headers:
    class_name,day_of_week,start_time,end_time,subject,teacher_id,teacher_name,room_number
    """
    content = await file.read()
    filename = file.filename.lower()
    imported_count = 0

    try:
        if filename.endswith(".json"):
            data = json.loads(content.decode("utf-8"))
            items = data if isinstance(data, list) else data.get("routines", [])
            for item in items:
                db.add_timetable_routine(
                    class_name=item.get("class_name", "CSE A"),
                    day_of_week=item.get("day_of_week", "Monday"),
                    start_time=item.get("start_time", "09:00"),
                    end_time=item.get("end_time", "10:00"),
                    subject=item.get("subject", "General"),
                    teacher_id=item.get("teacher_id"),
                    teacher_name=item.get("teacher_name"),
                    room_number=item.get("room_number", "Room 101")
                )
                imported_count += 1
        else:
            # Parse as CSV
            text = content.decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(text))
            for row in reader:
                # Clean keys
                clean_row = {k.strip().lower(): (v.strip() if v else "") for k, v in row.items() if k}
                class_name = clean_row.get("class_name") or clean_row.get("class") or clean_row.get("section")
                day = clean_row.get("day_of_week") or clean_row.get("day")
                start_time = clean_row.get("start_time") or clean_row.get("start")
                end_time = clean_row.get("end_time") or clean_row.get("end")
                subject = clean_row.get("subject") or clean_row.get("course") or "Lecture"

                if not (class_name and day and start_time and end_time):
                    continue

                teacher_id = clean_row.get("teacher_id") or clean_row.get("faculty_id") or None
                teacher_name = clean_row.get("teacher_name") or clean_row.get("faculty_name") or None
                room = clean_row.get("room_number") or clean_row.get("room") or "Room 101"

                # Attempt teacher lookup
                if teacher_id and not teacher_name:
                    t = db.get_teacher_by_id(teacher_id)
                    if t:
                        teacher_name = t.get("name")

                db.add_timetable_routine(
                    class_name=class_name,
                    day_of_week=day,
                    start_time=start_time,
                    end_time=end_time,
                    subject=subject,
                    teacher_id=teacher_id,
                    teacher_name=teacher_name,
                    room_number=room
                )
                imported_count += 1

        return {
            "success": True,
            "imported_count": imported_count,
            "count": imported_count,
            "message": f"Successfully imported {imported_count} timetable routine slots!"
        }
    except Exception as e:
        logger.error(f"Error parsing timetable file: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to process timetable file: {str(e)}")

@router.delete("/routine/{routine_id}")
async def delete_routine(routine_id: int, db: DatabaseManager = Depends(get_db)):
    """Delete a single timetable slot by ID."""
    success = db.delete_timetable_routine(routine_id)
    return {"success": success, "message": "Routine deleted"}

@router.delete("/routines/all")
async def clear_all_routines(db: DatabaseManager = Depends(get_db)):
    """Clear all timetable routines."""
    db.clear_all_timetable_routines()
    return {"success": True, "message": "All timetable routines cleared"}

@router.get("/status")
async def get_timetable_status(class_name: Optional[str] = None, db: DatabaseManager = Depends(get_db)):
    """
    Evaluates the active schedule for the current day and clock time.
    Calculates whether the scheduled teacher has arrived within the 5-minute grace period.
    Triggers 'is_late_alert' (blinking yellow warning) if teacher is absent after 5 minutes.
    """
    now = datetime.now()
    current_day = now.strftime("%A")  # e.g. "Monday"
    current_time_str = now.strftime("%H:%M")  # e.g. "09:15"
    current_minutes = now.hour * 60 + now.minute

    all_classes = ["CSE A", "CSE B", "CSE AIML", "CE", "ME", "ECE"]
    active_session = db.get_active_session()
    
    # Pre-fetch teachers for quick status matching
    all_teachers = db.list_teachers()
    teacher_map = {t["teacher_id"]: t for t in all_teachers}

    class_status_map = {}

    for cls in all_classes:
        routines = db.list_timetable_routines(class_name=cls, day_of_week=current_day)
        active_slot = None

        for r in routines:
            try:
                s_parts = [int(p) for p in r["start_time"].split(":")]
                e_parts = [int(p) for p in r["end_time"].split(":")]
                s_min = s_parts[0] * 60 + s_parts[1]
                e_min = e_parts[0] * 60 + e_parts[1]

                if s_min <= current_minutes < e_min:
                    active_slot = dict(r)
                    active_slot["start_minutes"] = s_min
                    active_slot["end_minutes"] = e_min
                    break
            except Exception:
                continue

        if active_slot:
            start_min = active_slot["start_minutes"]
            elapsed_minutes = current_minutes - start_min
            scheduled_teacher_id = active_slot.get("teacher_id")

            # Check if teacher is present
            teacher_present = False
            if active_session:
                if scheduled_teacher_id and active_session.get("teacher_id") == scheduled_teacher_id:
                    teacher_present = True
                elif not scheduled_teacher_id:
                    teacher_present = True

            # Check 5-minute late rule:
            # If elapsed >= 5 mins and teacher is not present -> Blinking Yellow Alert
            is_late_alert = (elapsed_minutes >= 5) and (not teacher_present)

            class_status_map[cls] = {
                "class_name": cls,
                "has_active_slot": True,
                "active_slot": active_slot,
                "start_time": active_slot.get("start_time"),
                "end_time": active_slot.get("end_time"),
                "elapsed_minutes": elapsed_minutes,
                "teacher_present": teacher_present,
                "is_late_alert": is_late_alert,
                "teacher_name": active_slot.get("teacher_name") or "Assigned Faculty",
                "teacher_id": scheduled_teacher_id,
                "subject": active_slot.get("subject"),
                "room_number": active_slot.get("room_number") or "Room 101"
            }
        else:
            class_status_map[cls] = {
                "class_name": cls,
                "has_active_slot": False,
                "active_slot": None,
                "start_time": None,
                "end_time": None,
                "elapsed_minutes": 0,
                "teacher_present": False,
                "is_late_alert": False,
                "teacher_name": None,
                "teacher_id": None,
                "subject": None,
                "room_number": None
            }

    target_status = class_status_map.get(class_name) if class_name else class_status_map.get("CSE A")

    return {
        "success": True,
        "current_day": current_day,
        "current_time": current_time_str,
        "active_session": active_session,
        "status": target_status,
        "classes": class_status_map
    }
