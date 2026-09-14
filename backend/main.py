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
    session_router, attendance_router, enrollment_router, diagnostics_router, timetable_router, init_all_routes
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("attendance.main")

# Global Application Context
server_start_time = time.time()
context: Dict[str, Any] = {}
active_websockets: List[WebSocket] = []
annotated_frame_lock = threading.Lock()
latest_annotated_jpeg: bytes = b""
is_inference_running = False
is_engine_enabled = True
inference_thread: Optional[threading.Thread] = None
last_spoof_broadcast_time = 0.0
last_spoof_reason = ""

def _generate_paused_jpeg() -> bytes:
    """Generates a standby frame when camera/vision pipeline is paused by user."""
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    img[:] = (15, 23, 42)  # Slate 900
    cx, cy = 320, 240
    cv2.rectangle(img, (cx - 190, cy - 65), (cx + 190, cy + 65), (30, 41, 59), -1)
    cv2.rectangle(img, (cx - 190, cy - 65), (cx + 190, cy + 65), (245, 158, 11), 2)
    cv2.putText(img, "AI ENGINE IN STANDBY", (cx - 150, cy - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.72, (245, 158, 11), 2)
    cv2.putText(img, "Camera released (Click 'Turn On' to resume)", (cx - 170, cy + 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.46, (148, 163, 184), 1)
    ret, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return buf.tobytes() if ret else b""

def start_vision_engine() -> bool:
    """Activates camera hardware and spawns continuous AI vision inference loop."""
    global is_inference_running, is_engine_enabled, inference_thread
    with annotated_frame_lock:
        if is_inference_running:
            return True
        cam: Optional[CameraStream] = context.get("camera")
        if cam and not cam.running:
            cam.start()
        is_inference_running = True
        is_engine_enabled = True
        inference_thread = threading.Thread(target=background_inference_loop, daemon=True, name="VisionInferenceThread")
        inference_thread.start()
        logger.info("AI Vision Engine and optical camera started successfully.")
        return True

def stop_vision_engine() -> bool:
    """Gracefully releases optical camera and pauses AI vision inference loop."""
    global is_inference_running, is_engine_enabled
    with annotated_frame_lock:
        is_inference_running = False
        is_engine_enabled = False
        cam: Optional[CameraStream] = context.get("camera")
        if cam and cam.running:
            cam.stop()
        logger.info("AI Vision Engine and camera stopped (standby mode, hardware released).")
        return True

def background_inference_loop():
    """Continuous edge vision loop running at native camera frame rate."""
    global latest_annotated_jpeg, is_inference_running, last_spoof_broadcast_time, last_spoof_reason
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

        # Broadcast spoof attempts with debouncing (at most 1 per 2.5s unless spoof reason changes)
        now_t = time.time()
        for tf in getattr(face_eng, "last_tracked_faces", []):
            if getattr(tf, "liveness_state", "") == "SPOOF":
                spoof_reason = getattr(tf, "liveness_reason", "Photo / Screen Spoof")
                if (now_t - last_spoof_broadcast_time > 2.5) or (spoof_reason != last_spoof_reason):
                    last_spoof_broadcast_time = now_t
                    last_spoof_reason = spoof_reason
                    logger.warning(f"Anti-Spoof Alert: Presentation attack blocked ({spoof_reason})")
                    broadcast_ws_event("SPOOF_DETECTED", {
                        "track_id": tf.track_id,
                        "reason": spoof_reason,
                        "timestamp": time.strftime("%H:%M:%S")
                    })

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
    for ws in list(active_websockets):
        try:
            future = asyncio.run_coroutine_threadsafe(ws.send_text(message), loop)
            def _check_result(f, socket=ws):
                try:
                    f.result()
                except Exception:
                    if socket in active_websockets:
                        active_websockets.remove(socket)
            future.add_done_callback(_check_result)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        if ws in active_websockets:
            active_websockets.remove(ws)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global loop, is_inference_running
    loop = asyncio.get_running_loop()

    # Suppress benign Windows socket disconnection noise and client drops
    def handle_async_exception(l, ctx):
        exc = ctx.get('exception')
        if isinstance(exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError)):
            return
        if exc and any(err in str(exc) for err in ("10054", "10053", "EndOfStream", "CancelledError")):
            return
        try:
            l.default_exception_handler(ctx)
        except Exception:
            pass
    loop.set_exception_handler(handle_async_exception)

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
    start_vision_engine()

    logger.info("AI Attendance System ready on Raspberry Pi 5.")
    yield

    # Shutdown
    stop_vision_engine()
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
app.include_router(timetable_router)

# Health & System Power Management Endpoints
@app.get("/api/health")
def get_health_status():
    """Returns real-time backend health, engine state, camera status, and uptime."""
    cam: Optional[CameraStream] = context.get("camera")
    return {
        "status": "online",
        "engine_active": is_inference_running,
        "is_engine_enabled": is_engine_enabled,
        "camera_active": cam.running if cam else False,
        "is_synthetic": cam.is_synthetic if cam else True,
        "camera_source": cam.src if cam else 0,
        "fps": cam.fps if cam else 0.0,
        "uptime_seconds": round(time.time() - server_start_time, 1)
    }

@app.post("/api/system/engine/toggle")
def toggle_vision_engine(payload: Optional[Dict[str, Any]] = None):
    """Toggles AI vision engine and optical camera between active and standby mode."""
    target_state = None
    if payload:
        if "active" in payload:
            target_state = bool(payload["active"])
        elif "enable" in payload:
            target_state = bool(payload["enable"])
        elif "action" in payload:
            target_state = (payload["action"] == "start" or payload["action"] == "on")
    
    if target_state is None:
        target_state = not is_inference_running

    if target_state:
        start_vision_engine()
        msg = "AI Vision Engine and camera activated"
    else:
        stop_vision_engine()
        msg = "AI Vision Engine and camera paused (standby mode, camera released)"

    cam: Optional[CameraStream] = context.get("camera")
    return {
        "success": True,
        "engine_active": is_inference_running,
        "is_engine_enabled": is_engine_enabled,
        "camera_active": cam.running if cam else False,
        "message": msg
    }

@app.post("/api/system/shutdown")
def shutdown_system():
    """Gracefully terminates the FastAPI and Uvicorn backend process."""
    stop_vision_engine()
    fp_mgr = context.get("fingerprint_manager")
    if fp_mgr and fp_mgr.driver:
        try:
            fp_mgr.driver.disconnect()
        except Exception:
            pass

    def _delayed_exit():
        time.sleep(0.5)
        logger.info("Process terminated via user /api/system/shutdown request.")
        os._exit(0)

    threading.Thread(target=_delayed_exit, daemon=True).start()
    return {
        "success": True,
        "message": "Backend server process is shutting down"
    }

# Video Streaming Endpoint (MJPEG)
async def generate_mjpeg_frames():
    try:
        while True:
            if is_inference_running:
                with annotated_frame_lock:
                    frame_bytes = latest_annotated_jpeg
                if frame_bytes:
                    yield (b"--frame\r\n"
                           b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
                await asyncio.sleep(0.033)  # ~30 FPS
            else:
                paused_bytes = _generate_paused_jpeg()
                if paused_bytes:
                    yield (b"--frame\r\n"
                           b"Content-Type: image/jpeg\r\n\r\n" + paused_bytes + b"\r\n")
                await asyncio.sleep(0.5)  # 2 FPS standby
    except (asyncio.CancelledError, GeneratorExit, Exception):
        pass

@app.get("/api/video/feed")
async def video_feed():
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
    except (WebSocketDisconnect, ConnectionResetError, Exception):
        pass
    finally:
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
