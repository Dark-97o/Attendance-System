"""
Main FastAPI Application Server for Raspberry Pi 5 AI Attendance System.
Hosts MJPEG Video Stream, WebSockets for Live UI Updates, REST APIs, and Static Frontend.
"""

import os
import time
import json
import asyncio
import logging
import threading
import cv2
import numpy as np
from contextlib import asynccontextmanager
from typing import List, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from database.db import init_db
from database.models import DatabaseManager
from fingerprint.fingerprint_manager import FingerprintManager
from engine.camera import CameraStream
from engine.face_engine import FaceEngine
from engine.attendance_manager import AttendanceManager
from backend.routes import (
    session_router, attendance_router, enrollment_router, diagnostics_router, init_all_routes
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("attendance.main")

# Global Application Context
context: Dict[str, Any] = {}
active_websockets: List[WebSocket] = []
annotated_frame_lock = threading.Lock()
latest_annotated_jpeg: bytes = b""
is_inference_running = False

def background_inference_loop():
    """Continuous edge vision loop running at native camera frame rate."""
    global latest_annotated_jpeg, is_inference_running
    cam: CameraStream = context["camera"]
    face_eng: FaceEngine = context["face_engine"]
    att_mgr: AttendanceManager = context["attendance_manager"]

    logger.info("Background Vision & Attendance Pipeline started.")
    loop_count = 0

    while is_inference_running:
        ret, frame = cam.read()
        if not ret or frame is None:
            time.sleep(0.02)
            continue

        # Process frame through lighting compensation, face recognition, and tracking
        try:
            annotated_frame, recognized_students, lighting_metrics = face_eng.process_frame(frame)
        except Exception as err:
            logger.warning(f"Transient vision inference error: {err}")
            annotated_frame = frame.copy()
            recognized_students = []
            lighting_metrics = {"mean_lum": 0.0, "contrast": 0.0, "is_night_mode": False}

        # Feed recognized students into attendance session state machine
        if recognized_students:
            att_mgr.process_recognized_students(recognized_students)

        # Draw session active banner on video feed
        session_status = att_mgr.get_session_status()
        h, w = annotated_frame.shape[:2]
        if session_status["session_active"]:
            sess = session_status["session"]
            banner_text = f"SESSION ACTIVE: {sess['course_code']} | TEACHER: {sess.get('teacher_name', 'Faculty')}"
            cv2.rectangle(annotated_frame, (0, 0), (w, 32), (39, 174, 96), -1)
            cv2.putText(annotated_frame, banner_text, (15, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        else:
            banner_text = "SESSION INACTIVE (WAITING FOR TEACHER FINGERPRINT AUTH)"
            cv2.rectangle(annotated_frame, (0, 0), (w, 32), (41, 128, 185), -1)
            cv2.putText(annotated_frame, banner_text, (15, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

        # Encode to JPEG for MJPEG stream
        ret_enc, jpeg = cv2.imencode(".jpg", annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ret_enc:
            with annotated_frame_lock:
                latest_annotated_jpeg = jpeg.tobytes()

        loop_count += 1
        time.sleep(0.01)

def broadcast_ws_event(event_type: str, data: Dict[str, Any]):
    """Pushes real-time events to all connected touchscreen and dashboard WebSockets."""
    message = json.dumps({"type": event_type, "payload": data})
    disconnected = []
    for ws in active_websockets:
        try:
            asyncio.run_coroutine_threadsafe(ws.send_text(message), loop)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        if ws in active_websockets:
            active_websockets.remove(ws)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global loop, is_inference_running
    loop = asyncio.get_running_loop()

    # 1. Initialize Database
    init_db()
    db = DatabaseManager()

    # 2. Initialize Hardware Subsystems
    fp_mgr = FingerprintManager(db)
    cam = CameraStream(src=0, width=640, height=480, fps_target=30)
    cam.start()

    face_eng = FaceEngine(db)
    att_mgr = AttendanceManager(db, fp_mgr)

    # Subscribe WebSocket broadcaster to attendance manager events
    att_mgr.subscribe(broadcast_ws_event)

    # 3. Store in Context
    context.update({
        "db": db,
        "fingerprint_manager": fp_mgr,
        "camera": cam,
        "face_engine": face_eng,
        "attendance_manager": att_mgr
    })

    init_all_routes(context)

    # 4. Start Background Vision Inference Thread
    is_inference_running = True
    vision_thread = threading.Thread(target=background_inference_loop, daemon=True, name="VisionInferenceThread")
    vision_thread.start()

    logger.info("AI Attendance System ready on Raspberry Pi 5.")
    yield

    # Shutdown
    is_inference_running = False
    cam.stop()
    if fp_mgr.driver:
        fp_mgr.driver.disconnect()
    logger.info("AI Attendance System shutdown completed.")

app = FastAPI(
    title="Raspberry Pi 5 AI Face Recognition Attendance System",
    description="Edge-computing attendance tracking system gated by R307 fingerprint sensor.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(session_router)
app.include_router(attendance_router)
app.include_router(enrollment_router)
app.include_router(diagnostics_router)

# Video Streaming Endpoint (MJPEG)
def generate_mjpeg_frames():
    while is_inference_running:
        with annotated_frame_lock:
            frame_bytes = latest_annotated_jpeg
        if frame_bytes:
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
        time.sleep(0.033)  # ~30 FPS

@app.get("/api/video/feed")
def video_feed():
    """Real-time annotated video stream with recognition bounding boxes and HUD watermark."""
    return StreamingResponse(
        generate_mjpeg_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

# Real-Time WebSocket for Live Touchscreen Dashboard
@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        # Send initial state
        att_mgr: AttendanceManager = context["attendance_manager"]
        await websocket.send_text(json.dumps({
            "type": "INITIAL_STATE",
            "payload": att_mgr.get_session_status()
        }))
        while True:
            # Keepalive / ping-pong
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        if websocket in active_websockets:
            active_websockets.remove(websocket)
    except Exception:
        if websocket in active_websockets:
            active_websockets.remove(websocket)

# Static files for 7-Inch Touchscreen UI
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
FACES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "faces")
os.makedirs(FACES_DIR, exist_ok=True)

if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
    css_path = os.path.join(FRONTEND_DIR, "css")
    js_path = os.path.join(FRONTEND_DIR, "js")
    assets_path = os.path.join(FRONTEND_DIR, "assets")
    if os.path.exists(css_path):
        app.mount("/css", StaticFiles(directory=css_path), name="css")
    if os.path.exists(js_path):
        app.mount("/js", StaticFiles(directory=js_path), name="js")
    if os.path.exists(assets_path):
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

if os.path.exists(FACES_DIR):
    app.mount("/faces", StaticFiles(directory=FACES_DIR), name="faces")

@app.get("/")
def serve_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Attendance System Backend Running."}
