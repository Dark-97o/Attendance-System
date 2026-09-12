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
    fingerprint_id: Optional[int] = 1

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
    for t in teachers:
        if t.get("photo_path"):
            filename = os.path.basename(t["photo_path"])
            t["photo_url"] = f"/faces/{filename}"
        else:
            t["photo_url"] = None
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
        fingerprint_id=req.fingerprint_id or 1
    )

    # Enroll in sensor if hardware present
    enroll_success, enroll_msg = fp_mgr.enroll_teacher_fingerprint(req.teacher_id, req.fingerprint_id or 1)
    return {
        "success": True,
        "message": f"Faculty {req.name} registered successfully",
        "fingerprint_status": enroll_msg
    }

@router.delete("/teacher/{teacher_id}")
def delete_teacher(teacher_id: str):
    """Deletes a registered teacher/faculty member."""
    ctx = get_context()
    db = ctx["db"]
    face_eng = ctx.get("face_engine")

    success = db.delete_teacher(teacher_id)
    if face_eng:
        face_eng.refresh_enrolled_cache()
    return {"success": success, "message": f"Faculty {teacher_id} removed"}

@router.post("/face")
async def enroll_face_from_upload(
    student_id: Optional[str] = Form(None),
    teacher_id: Optional[str] = Form(None),
    entity_type: Optional[str] = Form("student"),
    name: Optional[str] = Form(None),
    roll_number: Optional[str] = Form(None),
    class_section: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    file: UploadFile = File(...)
):
    """Enrolls face for either a student or teacher from an uploaded photo (JPG/PNG)."""
    ctx = get_context()
    face_eng = ctx["face_engine"]
    db = ctx["db"]

    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img_bgr is None:
        raise HTTPException(status_code=400, detail="Invalid image file")

    faces_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "faces")
    os.makedirs(faces_dir, exist_ok=True)

    is_teacher = (entity_type == "teacher") or bool(teacher_id)
    if is_teacher:
        tid = teacher_id or student_id or f"T_{int(time.time())}"
        tname = name or f"Faculty {tid}"
        tdept = department or "CSE"
        photo_filename = f"teacher_{tid}_{int(time.time())}.jpg"
        photo_path = os.path.join(faces_dir, photo_filename)
        cv2.imwrite(photo_path, img_bgr)

        db.register_teacher(teacher_id=tid, name=tname, department=tdept, photo_path=photo_path)
        success, msg = face_eng.enroll_face_image(tid, img_bgr)
        identifier = tid
        display_name = tname
    else:
        sid = student_id or f"S_{int(time.time())}"
        sname = name or f"Student {sid}"
        sroll = roll_number or sid
        ssec = class_section or "CSE A"
        photo_filename = f"{sid}_{int(time.time())}.jpg"
        photo_path = os.path.join(faces_dir, photo_filename)
        cv2.imwrite(photo_path, img_bgr)

        db.register_student(student_id=sid, name=sname, roll_number=sroll, class_section=ssec, photo_path=photo_path)
        success, msg = face_eng.enroll_face_image(sid, img_bgr)
        identifier = sid
        display_name = sname

    # Generate preview base64
    ret_enc, buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
    b64_str = base64.b64encode(buf).decode("utf-8") if ret_enc else ""

    return {
        "success": success,
        "message": f"Successfully enrolled face for {display_name}!",
        "id": identifier,
        "student_id": identifier,
        "name": display_name,
        "photo_preview": f"data:image/jpeg;base64,{b64_str}" if b64_str else None
    }

@router.post("/snap")
def snap_and_enroll(payload: Dict[str, Any]):
    """Captures current frame from camera stream and enrolls face for student or teacher."""
    ctx = get_context()
    cam = ctx["camera"]
    face_eng = ctx["face_engine"]
    db = ctx["db"]

    ret, frame = cam.read()
    if not ret or frame is None:
        raise HTTPException(status_code=500, detail="Could not capture frame from optical camera")

    is_teacher = payload.get("entity_type") == "teacher" or "teacher_id" in payload
    faces_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "faces")
    os.makedirs(faces_dir, exist_ok=True)

    if is_teacher:
        tid = payload.get("teacher_id") or payload.get("id") or f"T_{int(time.time())}"
        tname = payload.get("name") or f"Faculty {tid}"
        tdept = payload.get("department") or "CSE"
        slot = int(payload.get("fingerprint_id", 1))

        photo_filename = f"teacher_{tid}_{int(time.time())}.jpg"
        photo_path = os.path.join(faces_dir, photo_filename)
        cv2.imwrite(photo_path, frame)

        db.register_teacher(teacher_id=tid, name=tname, department=tdept, fingerprint_id=slot, photo_path=photo_path)
        success, msg = face_eng.enroll_face_image(tid, frame)
        identifier = tid
        display_name = tname
    else:
        sid = payload.get("student_id") or payload.get("id") or f"S_{int(time.time())}"
        sname = payload.get("name") or f"Student {sid}"
        sroll = payload.get("roll_number") or sid
        ssec = payload.get("class_section") or "CSE A"

        photo_filename = f"{sid}_{int(time.time())}.jpg"
        photo_path = os.path.join(faces_dir, photo_filename)
        cv2.imwrite(photo_path, frame)

        db.register_student(student_id=sid, name=sname, roll_number=sroll, class_section=ssec, photo_path=photo_path)
        success, msg = face_eng.enroll_face_image(sid, frame)
        identifier = sid
        display_name = sname

    preview_img = np.ascontiguousarray(frame.copy())
    faces = face_eng.detect_faces(preview_img)
    for (fx, fy, fw, fh) in faces:
        cv2.rectangle(preview_img, (fx, fy), (fx + fw, fy + fh), (16, 185, 129), 2)
        cv2.putText(preview_img, f"Captured: {display_name}", (fx, fy - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (16, 185, 129), 1)

    ret_enc, buf = cv2.imencode(".jpg", preview_img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    b64_str = base64.b64encode(buf).decode("utf-8") if ret_enc else ""

    return {
        "success": success,
        "message": f"Successfully enrolled face for {display_name}!",
        "id": identifier,
        "student_id": identifier,
        "name": display_name,
        "photo_preview": f"data:image/jpeg;base64,{b64_str}" if b64_str else None,
        "faces_detected": len(faces)
    }

@router.post("/face/live-capture")
def enroll_face_from_live_camera(
    student_id: str = Form(...),
    name: Optional[str] = Form(None),
    roll_number: Optional[str] = Form(None),
    class_section: Optional[str] = Form(None)
):
    """Legacy endpoint supporting form-data live-capture."""
    return snap_and_enroll({
        "student_id": student_id,
        "name": name,
        "roll_number": roll_number,
        "class_section": class_section
    })

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

