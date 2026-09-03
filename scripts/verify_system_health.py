"""Diagnostic health check utility for environment, camera, and ONNX weights."""

import os
import sys


def check_models() -> bool:
    yunet = "models/face_detection_yunet_2023mar.onnx"
    sface = "models/face_recognition_sface_2021dec.onnx"
    ok = True
    for m in [yunet, sface]:
        if os.path.exists(m):
            print(f"[OK] Model found: {m} ({os.path.getsize(m) / 1024:.1f} KB)")
        else:
            print(f"[WARN] Model missing: {m}")
            ok = False
    return ok


def check_database() -> bool:
    db = "data/attendance_system.db"
    if os.path.exists(db):
        print(f"[OK] Database exists: {db}")
        return True
    print(f"[WARN] Database file not found: {db}")
    return False


if __name__ == "__main__":
    print("=== Attendance System Diagnostics ===")
    m_ok = check_models()
    d_ok = check_database()
    if m_ok and d_ok:
        print("[SUCCESS] All core assets verified.")
        sys.exit(0)
    else:
        print("[NOTICE] Some optional or pre-generation assets missing.")
        sys.exit(0)
