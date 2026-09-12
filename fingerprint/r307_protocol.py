"""
R307 Optical Fingerprint Sensor Protocol Specification.
Implements packet framing, checksum calculation, and command definitions.
"""

from enum import IntEnum
from typing import Tuple, Optional, List

HEADER = 0xEF01
DEFAULT_ADDRESS = 0xFFFFFFFF

class PacketPID(IntEnum):
    COMMAND = 0x01
    DATA = 0x02
    ACK = 0x07
    END_DATA = 0x08

class CommandCode(IntEnum):
    GEN_IMG = 0x01        # Collect finger image
    IMG_TO_TZ = 0x02      # Generate character file (buffer 1 or 2)
    MATCH = 0x03          # Match buffer 1 with buffer 2
    SEARCH = 0x04         # Search library for finger matching buffer
    REG_MODEL = 0x05      # Merge buffer 1 & 2 into template
    STORE = 0x06          # Store template into flash library
    LOAD_CHAR = 0x07      # Load template from library into buffer
    DELETE_CHAR = 0x0C    # Delete template(s)
    EMPTY = 0x0D          # Clear all enrolled fingerprints
    READ_SYS_PARA = 0x0E  # Read module parameters
    LED_CONTROL = 0x1B    # Control LED (breathing/on/off)
    HANDSHAKE = 0x16      # Protocol handshake

class ConfirmationCode(IntEnum):
    OK = 0x00
    PACKET_RECEIVE_ERROR = 0x01
    NO_FINGER = 0x02
    FAIL_TO_COLLECT = 0x03
    IMAGE_MESSY = 0x06
    FEATURE_FAIL = 0x07
    NO_MATCH = 0x09
    FIND_FAILED = 0x0A
    FAIL_TO_COMBINE = 0x0B
    BAD_ADDRESS = 0x0C
    DELETE_FAIL = 0x10
    CLEAR_FAIL = 0x11
    PASSWORD_ERROR = 0x13
    FLASH_ERROR = 0x18

CONFIRMATION_MESSAGES = {
    ConfirmationCode.OK: "Operation successful",
    ConfirmationCode.PACKET_RECEIVE_ERROR: "Packet receiving error",
    ConfirmationCode.NO_FINGER: "No finger on sensor",
    ConfirmationCode.FAIL_TO_COLLECT: "Failed to collect finger image",
    ConfirmationCode.IMAGE_MESSY: "Fingerprint image is too messy",
    ConfirmationCode.FEATURE_FAIL: "Failed to generate character file",
    ConfirmationCode.NO_MATCH: "No matching fingerprint found",
    ConfirmationCode.FIND_FAILED: "Fingerprint search failed",
    ConfirmationCode.FAIL_TO_COMBINE: "Failed to combine templates into model",
    ConfirmationCode.BAD_ADDRESS: "Bad memory address / Page ID out of range",
    ConfirmationCode.DELETE_FAIL: "Failed to delete template",
    ConfirmationCode.CLEAR_FAIL: "Failed to clear library",
}

def build_packet(pid: PacketPID, content: bytes, address: int = DEFAULT_ADDRESS) -> bytes:
    """Constructs a framed R307 packet with 16-bit checksum."""
    length = len(content) + 2  # Length includes content + 2 checksum bytes
    packet = bytearray()
    
    # 2 bytes Header (0xEF01)
    packet.append((HEADER >> 8) & 0xFF)
    packet.append(HEADER & 0xFF)
    
    # 4 bytes Device Address
    packet.append((address >> 24) & 0xFF)
    packet.append((address >> 16) & 0xFF)
    packet.append((address >> 8) & 0xFF)
    packet.append(address & 0xFF)
    
    # 1 byte PID
    packet.append(int(pid))
    
    # 2 bytes Length
    packet.append((length >> 8) & 0xFF)
    packet.append(length & 0xFF)
    
    # Content bytes
    packet.extend(content)
    
    # Checksum: sum of (PID + Length + Content)
    checksum = int(pid) + ((length >> 8) & 0xFF) + (length & 0xFF) + sum(content)
    checksum &= 0xFFFF
    
    packet.append((checksum >> 8) & 0xFF)
    packet.append(checksum & 0xFF)
    
    return bytes(packet)

def parse_ack_packet(raw_bytes: bytes) -> Tuple[bool, int, bytes, str]:
    """
    Parses an incoming acknowledge packet from R307.
    Returns: (is_valid, confirmation_code, payload_data, error_message)
    """
    if len(raw_bytes) < 9:
        return False, -1, b"", "Packet too short"
    
    # Find header 0xEF01
    idx = raw_bytes.find(b"\xef\x01")
    if idx == -1 or len(raw_bytes) - idx < 9:
        return False, -1, b"", "Header 0xEF01 not found"
    
    data = raw_bytes[idx:]
    pid = data[6]
    length = (data[7] << 8) | data[8]
    
    expected_total = 9 + length
    if len(data) < expected_total:
        return False, -1, b"", f"Incomplete packet: expected {expected_total} bytes, got {len(data)}"
    
    confirmation_code = data[9]
    payload = data[10 : expected_total - 2]
    received_checksum = (data[expected_total - 2] << 8) | data[expected_total - 1]
    
    # Calculate expected checksum
    calc_sum = pid + (length >> 8) + (length & 0xFF) + confirmation_code + sum(payload)
    calc_sum &= 0xFFFF
    
    if calc_sum != received_checksum:
        return False, confirmation_code, payload, f"Checksum mismatch: {calc_sum:#04x} vs {received_checksum:#04x}"
    
    status_msg = CONFIRMATION_MESSAGES.get(confirmation_code, f"Code 0x{confirmation_code:02X}")
    return True, confirmation_code, payload, status_msg
