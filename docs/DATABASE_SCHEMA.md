# Database Schema & Entity Relationships

The Attendance System leverages an ACID-compliant SQLite relational database with Foreign Key enforcement and Write-Ahead Logging (WAL) enabled.

```mermaid
erDiagram
    STUDENTS ||--o{ FACE_EMBEDDINGS : "has vectors"
    STUDENTS ||--o{ ATTENDANCE_RECORDS : "logs attendance"
    TEACHERS ||--o{ TIMETABLE_ROUTINES : "conducts"
    TEACHERS ||--o{ LECTURE_SESSIONS : "authenticates"
    LECTURE_SESSIONS ||--o{ ATTENDANCE_RECORDS : "contains"

    STUDENTS {
        string student_id PK
        string name
        string roll_number
        string email
        string class_section
        string photo_path
        timestamp created_at
    }

    TEACHERS {
        string teacher_id PK
        string name
        string department
        int fingerprint_id UK
        string photo_path
        timestamp created_at
    }

    FACE_EMBEDDINGS {
        int id PK
        string student_id FK
        text embedding_json
        timestamp created_at
    }

    LECTURE_SESSIONS {
        int id PK
        string session_token UK
        string teacher_id FK
        string subject
        string class_section
        string status
        timestamp started_at
        timestamp ended_at
    }

    ATTENDANCE_RECORDS {
        int id PK
        string student_id FK
        int session_id FK
        string status
        string method
        float confidence
        timestamp timestamp
    }
```

## Pragma Optimizations
- `PRAGMA foreign_keys = ON;`
- `PRAGMA journal_mode = WAL;`
- `PRAGMA synchronous = NORMAL;`
