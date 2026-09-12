import os
import cv2
import time
import base64
import numpy as np
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

router = APIRouter(prefix="/api/enroll", tags=["Enrollment"])

_context: Dict[str, Any] = {}

def set_router_context(app_context: Dict[str, Any]):
    global _context
    _context = app_context

def get_context():
    return _context

class RegisterStudentRequest(BaseModel):
    student_id: str
    name: str
    roll_number: str
    class_section: str

class RegisterTeacherRequest(BaseModel):
    teacher_id: str
    name: str
    department: str
    fingerprint_id: int

@router.get("/students")
def list_students():
    ctx = get_context()
    students = ctx["db"].list_students()
    for s in students:
        if s.get("photo_path"):
            filename = os.path.basename(s["photo_path"])
            s["photo_url"] = f"/faces/{filename}"
        else:
            s["photo_url"] = None
    return {"students": students, "total": len(students)}

@router.get("/teachers")
def list_teachers():
    ctx = get_context()
    teachers = ctx["db"].list_teachers()
    return {"teachers": teachers, "total": len(teachers)}

@router.post("/student")
def register_student(req: RegisterStudentRequest):
    ctx = get_context()
    db = ctx["db"]
    success = db.register_student(
        student_id=req.student_id,
        name=req.name,
        roll_number=req.roll_number,
        class_section=req.class_section
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to register student")
    return {"message": f"Student {req.name} registered successfully", "student_id": req.student_id}

@router.post("/teacher")
def register_teacher(req: RegisterTeacherRequest):
    ctx = get_context()
    db = ctx["db"]
    fp_mgr = ctx["fingerprint_manager"]

    # Register in DB
    db.register_teacher(
        teacher_id=req.teacher_id,
        name=req.name,
        department=req.department,
        fingerprint_id=req.fingerprint_id
    )

    # Enroll in sensor if hardware present
    enroll_success, enroll_msg = fp_mgr.enroll_teacher_fingerprint(req.teacher_id, req.fingerprint_id)
    return {
        "message": f"Faculty {req.name} registered",
        "fingerprint_status": enroll_msg
    }

@router.post("/face")
async def enroll_face_from_upload(
    student_id: str = Form(...),
    name: Optional[str] = Form(None),
    roll_number: Optional[str] = Form(None),
    class_section: Optional[str] = Form(None),
    file: UploadFile = File(...)
):
    """Enrolls face from an uploaded photo (JPG/PNG)."""
    ctx = get_context()
    face_eng = ctx["face_engine"]
    db = ctx["db"]

    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img_bgr is None:
        raise HTTPException(status_code=400, detail="Invalid image file")

    # Ensure student profile exists or update with provided details
    student_name = name or f"Student {student_id}"
    student_roll = roll_number or student_id
    student_sec = class_section or "Active"
    db.register_student(
        student_id=student_id,
        name=student_name,
        roll_number=student_roll,
        class_section=student_sec
    )

    # Save photo to data/faces directory
    faces_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "faces")
    os.makedirs(faces_dir, exist_ok=True)
    photo_filename = f"{student_id}_{int(time.time())}.jpg"
    photo_path = os.path.join(faces_dir, photo_filename)
    cv2.imwrite(photo_path, img_bgr)

    # Update student photo path
    with db._get_conn() as conn:
        conn.cursor().execute("UPDATE students SET photo_path = ? WHERE student_id = ?", (photo_path, student_id))
        conn.commit()

    success, msg = face_eng.enroll_face_image(student_id, img_bgr)

    # Generate preview base64
    ret_enc, buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
    b64_str = base64.b64encode(buf).decode("utf-8") if ret_enc else ""

    return {
        "success": success,
        "message": f"Successfully enrolled face for {student_name}!",
        "student_id": student_id,
        "photo_preview": f"data:image/jpeg;base64,{b64_str}" if b64_str else None
    }

@router.post("/face/live-capture")
def enroll_face_from_live_camera(
    student_id: str = Form(...),
    name: Optional[str] = Form(None),
    roll_number: Optional[str] = Form(None),
    class_section: Optional[str] = Form(None)
):
    """Captures the current frame from the camera stream, saves it, and enrolls the student face."""
    ctx = get_context()
    cam = ctx["camera"]
    face_eng = ctx["face_engine"]
    db = ctx["db"]

    # 1. Grab camera frame
    ret, frame = cam.read()
    if not ret or frame is None:
        raise HTTPException(status_code=500, detail="Could not capture frame from optical camera")

    # 2. Register / update student record
    student_name = name or f"Student {student_id}"
    student_roll = roll_number or student_id
    student_sec = class_section or "Active"
    db.register_student(
        student_id=student_id,
        name=student_name,
        roll_number=student_roll,
        class_section=student_sec
    )

    # 3. Save photo to data/faces directory
    faces_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "faces")
    os.makedirs(faces_dir, exist_ok=True)
    photo_filename = f"{student_id}_{int(time.time())}.jpg"
    photo_path = os.path.join(faces_dir, photo_filename)
    cv2.imwrite(photo_path, frame)

    # 4. Update student photo path
    with db._get_conn() as conn:
        conn.cursor().execute("UPDATE students SET photo_path = ? WHERE student_id = ?", (photo_path, student_id))
        conn.commit()

    # 5. Enroll face embedding into engine
    success, msg = face_eng.enroll_face_image(student_id, frame)

    # 6. Generate preview thumbnail with face box
    preview_img = np.ascontiguousarray(frame.copy())
    faces = face_eng.detect_faces(preview_img)
    for (fx, fy, fw, fh) in faces:
        cv2.rectangle(preview_img, (fx, fy), (fx + fw, fy + fh), (0, 240, 255), 2)
        cv2.putText(preview_img, f"Captured: {student_name}", (fx, fy - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 240, 255), 1)

    ret_enc, buf = cv2.imencode(".jpg", preview_img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    b64_str = base64.b64encode(buf).decode("utf-8") if ret_enc else ""

    return {
        "success": success,
        "message": f"Successfully enrolled face for {student_name}!",
        "student_id": student_id,
        "name": student_name,
        "roll_number": student_roll,
        "photo_preview": f"data:image/jpeg;base64,{b64_str}" if b64_str else None,
        "faces_detected": len(faces)
    }

@router.delete("/student/{student_id}")
def delete_student(student_id: str):
    """Deletes a specific student, associated embeddings, attendance records, and photo."""
    ctx = get_context()
    db = ctx["db"]
    face_eng = ctx["face_engine"]

    success = db.delete_student(student_id)
    face_eng.refresh_enrolled_cache()
    return {"success": success, "message": f"Student {student_id} and biometric data deleted"}

@router.delete("/students/all")
def delete_all_enrolled_students():
    """Deletes all enrolled students, embeddings, and face photos."""
    ctx = get_context()
    db = ctx["db"]
    face_eng = ctx["face_engine"]

    success = db.delete_all_students()
    face_eng.refresh_enrolled_cache()
    return {"success": success, "message": "All enrolled students and biometric face data deleted"}

