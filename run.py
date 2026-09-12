"""
One-click Application Runner for Raspberry Pi 5 AI Attendance System.
Launches the FastAPI backend with uvicorn server.
"""

import sys
import uvicorn
import logging

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    print("=" * 70)
    print("   AI Face Recognition Attendance System - Raspberry Pi 5")
    print("   R307 Optical Fingerprint Gated Edge Vision Architecture")
    print("=" * 70)
    import os
    port = int(os.environ.get("PORT", 8080))
    print(f"-> Starting web server on http://0.0.0.0:{port}")
    print(f"-> Touchscreen Kiosk UI: http://localhost:{port}")
    print(f"-> Interactive API Docs:  http://localhost:{port}/docs")
    print("=" * 70)

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        access_log=True
    )
