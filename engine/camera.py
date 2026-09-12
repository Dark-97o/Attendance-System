"""
Threaded Camera Ingestion Module for Raspberry Pi 5.
Supports USB Cameras, Pi Camera Modules (CSI/V4L2), and an interactive Synthetic Classroom Feed.
"""

import time
import math
import logging
import threading
import cv2
import numpy as np
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger("attendance.camera")

class CameraStream:
    """Asynchronous camera stream handler with thread-safe frame access."""

    def __init__(self, src: Any = 0, width: int = 640, height: int = 480, fps_target: int = 30):
        self.src = src
        self.width = width
        self.height = height
        self.fps_target = fps_target
        
        self.cap: Optional[cv2.VideoCapture] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        self.frame: Optional[np.ndarray] = None
        self.fps = 0.0
        self.frame_count = 0
        self.is_synthetic = False
        self._sim_step = 0

    def start(self) -> bool:
        """Starts background frame acquisition thread."""
        if self.running:
            return True

        # Attempt to open physical capture source
        opened = False
        try:
            if isinstance(self.src, int) or (isinstance(self.src, str) and self.src.isdigit()):
                dev_idx = int(self.src)
                # Use DirectShow on Windows or V4L2 on Linux for faster initialization
                if cv2.CAP_DSHOW is not None and hasattr(cv2, 'CAP_DSHOW'):
                    self.cap = cv2.VideoCapture(dev_idx, cv2.CAP_DSHOW)
                else:
                    self.cap = cv2.VideoCapture(dev_idx)
            else:
                self.cap = cv2.VideoCapture(self.src)

            if self.cap and self.cap.isOpened():
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                self.cap.set(cv2.CAP_PROP_FPS, self.fps_target)
                opened = True
                self.is_synthetic = False
                logger.info(f"Connected to physical camera source {self.src} ({self.width}x{self.height})")
        except Exception as e:
            logger.warning(f"Could not open physical camera {self.src}: {e}")

        if not opened:
            self.is_synthetic = True
            logger.info("Initializing Synthetic Classroom Video Feed for development/demonstration...")

        self.running = True
        self.thread = threading.Thread(target=self._update_loop, daemon=True, name="CameraThread")
        self.thread.start()
        return True

    def stop(self):
        """Stops background thread and releases camera."""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        if self.cap and self.cap.isOpened():
            self.cap.release()
        self.cap = None

    def switch_source(self, new_src: Any) -> bool:
        """Dynamically switches camera source without restarting background thread."""
        with self.lock:
            if self.cap is not None:
                try:
                    self.cap.release()
                except Exception as e:
                    logger.debug(f"Error releasing camera: {e}")
            self.cap = None
            self.frame = None

            # Small delay for OS driver to release hardware handle
            time.sleep(0.2)

            if isinstance(new_src, str) and new_src.isdigit():
                self.src = int(new_src)
            else:
                self.src = new_src

            opened = False
            try:
                if isinstance(self.src, int):
                    # Try CAP_DSHOW first on Windows for robust switching and fast startup
                    if hasattr(cv2, 'CAP_DSHOW'):
                        self.cap = cv2.VideoCapture(self.src, cv2.CAP_DSHOW)
                    if not self.cap or not self.cap.isOpened():
                        self.cap = cv2.VideoCapture(self.src)
                else:
                    self.cap = cv2.VideoCapture(self.src)

                if self.cap and self.cap.isOpened():
                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                    self.cap.set(cv2.CAP_PROP_FPS, self.fps_target)
                    opened = True
                    self.is_synthetic = False
                    logger.info(f"Successfully switched to camera source {self.src}")
            except Exception as e:
                logger.warning(f"Failed to switch to camera {self.src}: {e}")

            if not opened:
                self.is_synthetic = True
                logger.warning(f"Could not open camera {self.src}; reverting to standby mode")
            return opened

    def _update_loop(self):
        last_time = time.time()
        frames_in_sec = 0

        while self.running:
            start_frame_time = time.time()

            if not self.is_synthetic and self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    with self.lock:
                        self.frame = frame
                else:
                    # Camera disconnected or EOF; fall back to synthetic
                    logger.warning("Physical camera read failed; falling back to synthetic feed")
                    self.is_synthetic = True
            else:
                # Physical camera standby frame
                frame = self._generate_standby_frame()
                with self.lock:
                    self.frame = frame

            self.frame_count += 1
            frames_in_sec += 1
            now = time.time()
            if now - last_time >= 1.0:
                self.fps = round(frames_in_sec / (now - last_time), 1)
                frames_in_sec = 0
                last_time = now

            # Throttle to target FPS
            elapsed = time.time() - start_frame_time
            sleep_time = (1.0 / self.fps_target) - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _generate_standby_frame(self) -> np.ndarray:
        """
        Generates a professional hardware standby test pattern when camera device
        is awaiting signal, disconnected, or initializing.
        """
        self._sim_step += 1
        img = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        # Subtle dark slate background
        img[:] = (18, 22, 30)

        # Center target box
        cx, cy = self.width // 2, self.height // 2
        cv2.rectangle(img, (cx - 160, cy - 80), (cx + 160, cy + 80), (35, 45, 60), -1)
        cv2.rectangle(img, (cx - 160, cy - 80), (cx + 160, cy + 80), (60, 80, 110), 1)

        # Crosshairs
        cv2.line(img, (cx - 30, cy), (cx + 30, cy), (0, 240, 255), 1)
        cv2.line(img, (cx, cy - 30), (cx, cy + 30), (0, 240, 255), 1)

        cv2.putText(img, "OPTICAL SENSOR STANDBY", (cx - 110, cy - 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        cv2.putText(img, "Awaiting Camera / V4L2 Signal", (cx - 115, cy + 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (148, 163, 184), 1)

        # Status text at bottom
        status_text = f"DEVICE: {self.src} | RES: {self.width}x{self.height} | STATUS: ACTIVE POLLING"
        cv2.putText(img, status_text, (20, self.height - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (100, 116, 139), 1)

        return img

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Returns the latest captured frame safely."""
        with self.lock:
            if self.frame is not None:
                return True, self.frame.copy()
            return False, None

    def get_info(self) -> Dict[str, Any]:
        """Returns stream health metrics."""
        return {
            "is_running": self.running,
            "fps": self.fps,
            "frame_count": self.frame_count,
            "is_synthetic": self.is_synthetic,
            "resolution": f"{self.width}x{self.height}",
            "source": str(self.src)
        }
