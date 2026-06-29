"""Application configuration loader for Attendance System.

Supports configuration via environment variables with sane local defaults.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SystemConfig:
    db_path: str = os.getenv("ATTENDANCE_DB_PATH", "data/attendance_system.db")
    faces_dir: str = os.getenv("ATTENDANCE_FACES_DIR", "data/faces")
    yunet_weights: str = os.getenv("YUNET_WEIGHTS_PATH", "models/face_detection_yunet_2023mar.onnx")
    sface_weights: str = os.getenv("SFACE_WEIGHTS_PATH", "models/face_recognition_sface_2021dec.onnx")
    
    # Biometric thresholds
    face_match_threshold: float = float(os.getenv("FACE_MATCH_THRESHOLD", "0.363"))
    liveness_ear_threshold: float = float(os.getenv("LIVENESS_EAR_THRESHOLD", "0.22"))
    liveness_variance_min: float = float(os.getenv("LIVENESS_VARIANCE_MIN", "85.0"))
    
    # Debounce window in seconds
    attendance_debounce_seconds: int = int(os.getenv("ATTENDANCE_DEBOUNCE_SEC", "300"))
    
    # Server port
    server_port: int = int(os.getenv("PORT", "8000"))
    debug_mode: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")


config = SystemConfig()
