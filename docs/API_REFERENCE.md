# REST API Reference Specification

## Base URL
`http://localhost:8000/api`

## Authentication & Gating
- `POST /api/sessions/start-by-fingerprint`
  - Body: `{"fingerprint_id": int}`
  - Response: `{"status": "active", "session_token": str, "teacher": {...}}`

## Biometric Attendance
- `POST /api/attendance/mark`
  - Body: `{"student_id": str, "session_id": int, "confidence": float}`
  - Response: `{"success": bool, "message": str}`
- `POST /api/attendance/reset`
  - Description: Resets current session cache and attendance tracking debounce map.

## Enrollment Endpoints
- `POST /api/enroll/student`
- `POST /api/enroll/teacher`
- `POST /api/enroll/snap` (Real-time camera frame capture and vector enrollment)

## Hardware Diagnostics
- `GET /api/diagnostics/cameras` (Lists available DirectShow video capture devices)
- `GET /api/diagnostics/system` (CPU, memory, disk telemetry)
