# AI Face Recognition Attendance System (Raspberry Pi 5)
### Edge-Native Dual-Biometric Architecture with R307 Fingerprint Session Gating

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Platform](https://img.shields.io/badge/Hardware-Raspberry%20Pi%205-red.svg)
![Sensor](https://img.shields.io/badge/Sensor-R307%20Optical%20UART-orange.svg)
![Framework](https://img.shields.io/badge/Backend-FastAPI-009688.svg)
![Display](https://img.shields.io/badge/UI-7--Inch%20Touchscreen%20Kiosk-purple.svg)

---

## 🌟 Overview
This project is an edge-computing AI Face Recognition Classroom Attendance System built specifically for the **Raspberry Pi 5 single-board computer**. It couples high-speed multi-face identification with physical **R307 Optical Fingerprint Sensor gating**, solving the fundamental vulnerability of uncontrolled automatic attendance marking.

### Key Capabilities:
- **Teacher-Gated Sessions:** An authorized instructor must scan their fingerprint on the R307 sensor to START and END a lecture session. Face recognition attendance is strictly locked when no lecture session is active.
- **Continuous Edge Face Pipeline:** 30+ FPS video ingestion with adaptive CIELAB CLAHE lighting compensation, multiscale detection, and 128D cosine similarity matching against enrolled student vectors.
- **Night-Vision & Low-Light Invariance:** Dynamic gamma modulation handles darkened classrooms during projector slides or infrared night-vision camera feeds.
- **Multi-Face Spatial IoU Tracker & Dwell-Time Hysteresis:** Distinguishes multiple students per frame and enforces a minimum persistent dwell threshold (3 frames) and 20s debounce cooldown to eliminate spurious passersby and duplicate logging.
- **Real-Time 7-Inch Touchscreen Kiosk:** Built for the official 800x480 / 1024x600 Pi Touchscreen with dark glassmorphic styling, live annotated video feed, KPI cards, real-time WebSocket attendance feed, interactive simulation triggers, and Chart.js trend graphs.
- **Dual-Mode Operation:** Automatically detects real R307 hardware over UART (`/dev/ttyAMA0`) or falls back to an interactive on-screen virtual scanner for testing on PC/Windows without hardware.

---

## 📂 Repository Structure

```
Attendance System/
├── backend/
│   ├── main.py                  # FastAPI application with WebSockets & MJPEG streaming
│   └── routes/
│       ├── sessions.py          # Lecture sessions & R307 fingerprint auth routes
│       ├── attendance.py        # Live attendance records, analytics, & CSV export
│       ├── enrollment.py        # Student, faculty, and face template enrollment
│       └── diagnostics.py       # Raspberry Pi 5 telemetry (CPU temp, RAM, FPS)
├── database/
│   ├── db.py                    # SQLite initialization & connection pool
│   └── models.py                # Data access object & database schema
├── engine/
│   ├── camera.py                # Threaded camera capture (USB/PiCam/Synthetic Feed)
│   ├── preprocessor.py          # Adaptive CIELAB CLAHE & dynamic gamma compensation
│   ├── tracker.py               # Centroid & spatial IoU multi-face tracker
│   ├── face_engine.py           # Edge face detection & cosine vector matcher
│   └── attendance_manager.py    # Session gating state machine & hysteresis logic
├── fingerprint/
│   ├── r307_protocol.py         # Exact R307 serial packet protocol & checksum
│   ├── r307_driver.py           # Hardware UART driver via pySerial
│   └── fingerprint_manager.py   # Hardware/Simulation dual-mode abstraction
├── frontend/
│   ├── index.html               # 7-inch Touchscreen Kiosk UI
│   ├── css/style.css            # Dark glassmorphic responsive styles
│   └── js/
│       ├── app.js               # WebSocket controller & REST client
│       └── charts.js            # Chart.js daily & weekly attendance graphs
├── docs/
│   ├── PATENT_SPECIFICATION.md  # Formal patent specification with 10 claims
│   ├── RESEARCH_PAPER.md        # IEEE-format academic paper with math & Pi 5 benchmarks
│   └── HARDWARE_SCHEMATIC.md    # Pinouts, wiring diagrams, & OS UART setup
├── requirements.txt
├── run.py                       # One-click startup script
└── README.md
```

---

## 🚀 Quick Start Guide

### 1. Clone or Open the Workspace
```bash
git clone <repo-url> "Attendance System"
cd "Attendance System"
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Launch the Edge Server
```bash
python run.py
```

Open your browser at:
- **7-Inch Touchscreen Kiosk UI:** [http://localhost:8080](http://localhost:8080)
- **Interactive OpenAPI Documentation:** [http://localhost:8080/docs](http://localhost:8080/docs)
- **Real-Time MJPEG Camera Stream:** [http://localhost:8080/api/video/feed](http://localhost:8080/api/video/feed)

---

## 🏛️ Real-World Production Workflow

1. **Faculty Registration:**
   - In the **Enrollment Studio** tab, register the instructor with their Name, Department, and assign an R307 Fingerprint Slot (e.g. Slot #1).
2. **Student Enrollment:**
   - In the **Enrollment Studio** tab, enter the Student ID, Full Name, University Roll Number, and Class Section.
   - Either click **"Live Camera Snap"** to capture the student's face directly from the live optical camera, or upload their passport photo.
   - The edge engine extracts the 128-dimensional biometric embedding and indexes it in the local SQLite database.
3. **Session Gating via R307 Fingerprint:**
   - The camera continuously monitors the classroom, but student attendance is strictly gated off.
   - The faculty member places their registered finger on the R307 optical prism.
   - The sensor transmits packet `0xEF01` over UART, verifies minutiae, and unlocks an active lecture session.
4. **Autonomous Attendance Logging:**
   - The edge camera feed scans students, applies CIELAB CLAHE lighting compensation, and matches faces against enrolled templates.
   - Spatial IoU tracking and dwell-time hysteresis verify that the student is physically attending the class (minimum 3 persistent frames).
   - Entry time, exit time, and confidence are recorded, debounced against duplicate writes, and broadcast to the dashboard via WebSockets.
5. **Session Conclusion & Export:**
   - At the conclusion of the lecture, the faculty member rescans their fingerprint to end the session.
   - The administrator or faculty member exports the finalized attendance sheet as CSV from the **Trends & Reports** tab.

---

## 📑 Research Paper & Patent Documentation
- **[PATENT_SPECIFICATION.md](docs/PATENT_SPECIFICATION.md)**: Full patent application draft including Field of Invention, Prior Art Limitations, Detailed Embodiments, and 10 Formal Claims.
- **[RESEARCH_PAPER.md](docs/RESEARCH_PAPER.md)**: Academic paper draft with mathematical formulations for CIELAB CLAHE, cosine metric, spatial IoU, and physical Raspberry Pi 5 benchmark tables.
- **[HARDWARE_SCHEMATIC.md](docs/HARDWARE_SCHEMATIC.md)**: Complete wiring pinout table (Pi 5 GPIO to R307 JST connector) and Raspberry Pi OS UART configuration.


---

## 🧠 SFace Deep Neural Face Recognition Upgrade
In addition to traditional Haar/YuNet detection, the system now integrates the OpenCV **SFace (ResNet-based 128D)** deep neural network (`face_recognition_sface_2021dec.onnx`):
- **Affine Landmark Alignment:** High-precision facial alignment using 5 facial landmarks (eyes, nose, mouth corners) before feature extraction.
- **128D Cosine Similarity Metric:** Strict thresholding (0.363 cosine distance / 0.637 similarity) eliminating false positives and identity misattributions.
- **Hardware DirectShow Device Enumeration:** Auto-discovery of edge and external webcams with real-time switching on the live monitor.
- **Department Specialization:** Configured for streamlined CSE and ECE departmental monitoring.
- **Retake Attendance & Reset:** Session-level and daily attendance record flushing with camera tracking debounce reset.
- **Automated Summary Dispatch:** Direct EmailJS integration for instantaneous lecture attendance reports.
