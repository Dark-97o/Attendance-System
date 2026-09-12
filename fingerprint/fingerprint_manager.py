"""
Fingerprint Manager with Hardware/Simulation dual-mode abstraction.
Ensures the attendance system runs flawlessly on Raspberry Pi 5 with physical R307
as well as during development/testing via simulated biometric triggers.
"""

import os
import time
import logging
import threading
from typing import Optional, Callable, Dict, Any, Tuple
from fingerprint.r307_driver import R307Driver
from database.models import DatabaseManager

logger = logging.getLogger("attendance.fingerprint_manager")

class FingerprintManager:
    """Manages teacher authentication via R307 optical fingerprint sensor over UART."""

    def __init__(self, db: DatabaseManager, port: Optional[str] = None, baudrate: int = 57600):
        self.db = db
        self.baudrate = baudrate
        self.driver: Optional[R307Driver] = None
        self.mode = "UART_STANDBY"
        self.is_monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self.on_teacher_authenticated: Optional[Callable[[Dict[str, Any]], None]] = None

        # Candidate serial ports for Raspberry Pi 5 UART
        candidate_ports = []
        env_port = os.environ.get("R307_PORT")
        if port:
            candidate_ports.append(port)
        elif env_port:
            candidate_ports.append(env_port)
        elif os.name == 'posix':
            for p in ["/dev/ttyAMA0", "/dev/serial0", "/dev/ttyUSB0"]:
                if os.path.exists(p):
                    candidate_ports.append(p)

        # Connect to physical R307 UART bus
        for candidate in candidate_ports:
            driver = R307Driver(port=candidate, baudrate=self.baudrate)
            if driver.connect():
                self.driver = driver
                self.mode = "UART_HARDWARE"
                logger.info(f"R307 Optical Fingerprint Sensor connected on {candidate} (57600 baud)")
                break

        if self.mode != "UART_HARDWARE":
            logger.info("R307 Sensor interface initialized in software bypass mode (Awaiting physical sensor signal)")

    def get_status(self) -> Dict[str, Any]:
        """Returns the current operational status of the fingerprint subsystem."""
        return {
            "mode": self.mode,
            "connected": self.driver.is_connected if self.driver else False,
            "port": self.driver.port if self.driver else "SIMULATED_UART",
            "baudrate": self.baudrate,
            "monitoring": self.is_monitoring
        }

    def scan_and_identify(self) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Scans finger on R307 and looks up the teacher in the database.
        Returns: (success, teacher_dict, message)
        """
        if self.mode == "HARDWARE" and self.driver and self.driver.is_connected:
            has_img, img_msg = self.driver.get_image()
            if not has_img:
                return False, None, img_msg
            
            has_tz, tz_msg = self.driver.image_to_tz(1)
            if not has_tz:
                return False, None, tz_msg
            
            matched, page_id, score, search_msg = self.driver.search_finger()
            if matched:
                teacher = self.db.get_teacher_by_fingerprint(page_id)
                if teacher:
                    logger.info(f"Teacher authenticated: {teacher['name']} (Page ID #{page_id}, Score: {score})")
                    return True, teacher, f"Authenticated: {teacher['name']}"
                else:
                    return False, None, f"Fingerprint #{page_id} matched in sensor but not registered to a teacher"
            return False, None, search_msg
        else:
            return False, None, "Awaiting hardware fingerprint on R307 sensor or specify registered fingerprint ID"

    def authenticate_teacher_fingerprint(self, fingerprint_id: int) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """Authenticates an enrolled faculty fingerprint slot and toggles active lecture session."""
        teacher = self.db.get_teacher_by_fingerprint(fingerprint_id)
        if teacher:
            logger.info(f"Faculty authenticated: {teacher['name']} (Fingerprint Slot #{fingerprint_id})")
            if self.on_teacher_authenticated:
                self.on_teacher_authenticated(teacher)
            return True, teacher, f"Authenticated: {teacher['name']}"
        return False, None, f"No faculty member registered for Fingerprint Slot #{fingerprint_id}"

    def enroll_teacher_fingerprint(self, teacher_id: str, target_fingerprint_id: int) -> Tuple[bool, str]:
        """Enrolls a teacher's finger into R307 and updates database."""
        teacher = self.db.get_teacher_by_id(teacher_id)
        if not teacher:
            return False, f"Teacher with ID {teacher_id} not found"

        if self.mode == "UART_HARDWARE" and self.driver and self.driver.is_connected:
            success, msg = self.driver.enroll_fingerprint(target_fingerprint_id)
            if not success:
                return False, msg
        else:
            msg = f"Assigned fingerprint slot #{target_fingerprint_id} to faculty {teacher['name']}"

        self.db.register_teacher(
            teacher_id=teacher["teacher_id"],
            name=teacher["name"],
            department=teacher["department"],
            fingerprint_id=target_fingerprint_id
        )
        return True, msg
