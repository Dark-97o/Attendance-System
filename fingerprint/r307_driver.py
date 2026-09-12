"""
R307 Optical Fingerprint Sensor Hardware Driver.
Communicates with R307 over UART serial bus on Raspberry Pi 5.
"""

import time
import logging
from typing import Optional, Tuple, Dict, Any
from fingerprint.r307_protocol import (
    HEADER, DEFAULT_ADDRESS, PacketPID, CommandCode,
    ConfirmationCode, build_packet, parse_ack_packet
)

logger = logging.getLogger("attendance.r307_driver")

class R307Driver:
    """Hardware driver for R307 UART fingerprint scanner."""

    def __init__(self, port: str = "/dev/ttyAMA0", baudrate: int = 57600, timeout: float = 0.2):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_conn = None
        self.is_connected = False

    def connect(self) -> bool:
        """Attempts to open serial port and verify handshake with R307."""
        try:
            import serial
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout
            )
            time.sleep(0.2)  # Wait for sensor stabilization
            
            # Test handshake
            if self.handshake():
                self.is_connected = True
                logger.info(f"R307 Fingerprint sensor successfully connected on {self.port} at {self.baudrate} baud")
                return True
            else:
                logger.warning(f"Port {self.port} opened, but R307 did not reply to handshake")
                if self.serial_conn and self.serial_conn.is_open:
                    self.serial_conn.close()
                self.serial_conn = None
                return False
        except Exception as e:
            logger.warning(f"Could not connect to physical R307 on {self.port}: {e}")
            if self.serial_conn and self.serial_conn.is_open:
                try:
                    self.serial_conn.close()
                except Exception:
                    pass
            self.serial_conn = None
            self.is_connected = False
            return False

    def disconnect(self):
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
        self.is_connected = False

    def _send_command(self, cmd_code: CommandCode, params: bytes = b"") -> Tuple[bool, int, bytes, str]:
        """Transmits a command packet and reads back the response."""
        if not self.serial_conn or not self.serial_conn.is_open:
            return False, -1, b"", "Serial port not open"
        
        payload = bytes([int(cmd_code)]) + params
        packet = build_packet(PacketPID.COMMAND, payload)
        
        self.serial_conn.reset_input_buffer()
        self.serial_conn.write(packet)
        self.serial_conn.flush()
        
        # Read response packet (at least 12 bytes expected)
        response = self.serial_conn.read(32)
        if not response:
            return False, -1, b"", "Sensor response timeout"
        
        return parse_ack_packet(response)

    def handshake(self) -> bool:
        """Sends handshake test command."""
        valid, code, _, _ = self._send_command(CommandCode.HANDSHAKE)
        return valid and code == ConfirmationCode.OK

    def get_image(self) -> Tuple[bool, str]:
        """Instructs sensor to scan finger on prism. Returns (success, status_message)."""
        valid, code, _, msg = self._send_command(CommandCode.GEN_IMG)
        if valid and code == ConfirmationCode.OK:
            return True, "Finger detected and imaged"
        elif code == ConfirmationCode.NO_FINGER:
            return False, "No finger present on sensor"
        return False, msg

    def image_to_tz(self, buffer_id: int = 1) -> Tuple[bool, str]:
        """Converts raw scanned image into feature template in buffer 1 or 2."""
        valid, code, _, msg = self._send_command(CommandCode.IMG_TO_TZ, bytes([buffer_id]))
        return (valid and code == ConfirmationCode.OK), msg

    def search_finger(self, start_page: int = 0, page_count: int = 300) -> Tuple[bool, int, int, str]:
        """
        Searches onboard library for a finger match against Buffer 1.
        Returns: (match_found, page_id, match_score, status_message)
        """
        # Params: [BufferID(1B), StartPage(2B), PageNum(2B)]
        params = bytes([
            0x01,
            (start_page >> 8) & 0xFF, start_page & 0xFF,
            (page_count >> 8) & 0xFF, page_count & 0xFF
        ])
        valid, code, payload, msg = self._send_command(CommandCode.SEARCH, params)
        if valid and code == ConfirmationCode.OK and len(payload) >= 4:
            page_id = (payload[0] << 8) | payload[1]
            match_score = (payload[2] << 8) | payload[3]
            return True, page_id, match_score, "Match found"
        return False, -1, 0, msg

    def enroll_fingerprint(self, target_page_id: int) -> Tuple[bool, str]:
        """
        Two-step enrollment workflow:
        1. Scan finger -> Buffer 1
        2. Wait remove & press again -> Buffer 2
        3. Merge buffers -> RegModel
        4. Store in Flash library at target_page_id
        """
        # Step 1: First scan
        logger.info("R307 Enrollment: Place finger on sensor (Scan 1)...")
        time.sleep(1.0)
        success, msg = self.get_image()
        if not success:
            return False, f"Scan 1 failed: {msg}"
        
        success, msg = self.image_to_tz(1)
        if not success:
            return False, f"Feature extraction 1 failed: {msg}"
        
        # Step 2: Second scan
        logger.info("R307 Enrollment: Remove and place same finger again (Scan 2)...")
        time.sleep(2.0)
        success, msg = self.get_image()
        if not success:
            return False, f"Scan 2 failed: {msg}"
        
        success, msg = self.image_to_tz(2)
        if not success:
            return False, f"Feature extraction 2 failed: {msg}"
        
        # Step 3: Combine models
        valid, code, _, msg = self._send_command(CommandCode.REG_MODEL)
        if not (valid and code == ConfirmationCode.OK):
            return False, f"Model combination failed: {msg}"
        
        # Step 4: Store in Flash
        params = bytes([0x01, (target_page_id >> 8) & 0xFF, target_page_id & 0xFF])
        valid, code, _, msg = self._send_command(CommandCode.STORE, params)
        if valid and code == ConfirmationCode.OK:
            return True, f"Fingerprint enrolled successfully at slot #{target_page_id}"
        return False, f"Store failed: {msg}"
