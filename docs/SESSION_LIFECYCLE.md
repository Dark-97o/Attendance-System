# Lecture Session Lifecycle & State Transitions

A lecture session must be authenticated via Teacher Fingerprint or Faculty Face Recognition before attendance logging is unlocked.

```mermaid
stateDiagram-v2
    [*] --> IDLE : System Initialized
    IDLE --> AUTHENTICATING : Teacher Scans Biometric
    AUTHENTICATING --> ACTIVE : Teacher Verified & Routine Matched
    AUTHENTICATING --> IDLE : Auth Failed / Unknown Teacher
    ACTIVE --> ATTENDANCE_LOGGING : Students Recognized by Vision Engine
    ATTENDANCE_LOGGING --> ACTIVE : Record Committed & Debounced
    ACTIVE --> CLOSED : Teacher Ends Session or Auto-Timeout
    CLOSED --> IDLE : Reset Session Cache
```

## Security Guarantees
- Attendance cannot be marked without an ACTIVE session.
- Student double-marking is locked via monotonic timestamp cooldowns.
