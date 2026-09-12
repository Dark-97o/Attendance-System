/**
 * AI Face Recognition Attendance System - Real-Time Dashboard Controller
 * Fully optimized for both Raspberry Pi 5 Edge Hardware (FastAPI) and Static GitHub Pages (Demo Mode)
 */

// Sound Synthesizer via Web Audio API (Zero external audio asset dependencies)
const AudioFx = {
    ctx: null,
    getCtx() {
        if (!this.ctx) {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (AudioContext) this.ctx = new AudioContext();
        }
        if (this.ctx && this.ctx.state === 'suspended') {
            this.ctx.resume();
        }
        return this.ctx;
    },
    playChime() {
        const ctx = this.getCtx();
        if (!ctx) return;
        try {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.type = 'sine';
            osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
            osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.15); // A5
            gain.gain.setValueAtTime(0.12, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
            osc.start();
            osc.stop(ctx.currentTime + 0.35);
        } catch (e) { }
    },
    playBeep() {
        const ctx = this.getCtx();
        if (!ctx) return;
        try {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.type = 'triangle';
            osc.frequency.setValueAtTime(1046.50, ctx.currentTime); // C6
            gain.gain.setValueAtTime(0.1, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15);
            osc.start();
            osc.stop(ctx.currentTime + 0.15);
        } catch (e) { }
    }
};

// Simulation Engine for GitHub Pages & Offline Kiosk Demos
const SimEngine = {
    active: false,
    session: null,
    sessionStartTime: null,
    cameraAngle: 0,
    nightVision: false,
    useWebcam: false,
    webcamStream: null,
    animationFrameId: null,

    // Initial student roster
    defaultStudents: [
        { student_id: "STU101", name: "Alex Chen", roll_number: "2024CS01", class_section: "CS-A", photo_path: null, confidence: 0.96 },
        { student_id: "STU102", name: "Priya Sharma", roll_number: "2024CS02", class_section: "CS-A", photo_path: null, confidence: 0.98 },
        { student_id: "STU103", name: "Marcus Vance", roll_number: "2024CS03", class_section: "CS-B", photo_path: null, confidence: 0.94 },
        { student_id: "STU104", name: "Sophia Rodriguez", roll_number: "2024CS04", class_section: "CS-A", photo_path: null, confidence: 0.97 },
        { student_id: "STU105", name: "Liam Davis", roll_number: "2024CS05", class_section: "CS-B", photo_path: null, confidence: 0.93 },
        { student_id: "STU106", name: "Aisha Patel", roll_number: "2024CS06", class_section: "CS-A", photo_path: null, confidence: 0.95 },
        { student_id: "STU107", name: "David Kim", roll_number: "2024CS07", class_section: "CS-B", photo_path: null, confidence: 0.92 },
        { student_id: "STU108", name: "Elena Rostova", roll_number: "2024CS08", class_section: "CS-A", photo_path: null, confidence: 0.96 }
    ],

    students: [],
    teachers: [
        { teacher_id: "TCH001", name: "Dr. Alan Turing", department: "Computer Science", fingerprint_id: 1 }
    ],
    records: [],
    simulatedFaces: [],
    lastSimMarkTime: 0,

    init() {
        this.active = true;
        // Load saved students or defaults
        try {
            const saved = localStorage.getItem('sim_students');
            this.students = saved ? JSON.parse(saved) : [...this.defaultStudents];
            const savedTeachers = localStorage.getItem('sim_teachers');
            if (savedTeachers) this.teachers = JSON.parse(savedTeachers);
            const savedRecords = localStorage.getItem('sim_records');
            this.records = savedRecords ? JSON.parse(savedRecords) : [];
        } catch (e) {
            this.students = [...this.defaultStudents];
        }

        // Initialize moving face targets for camera simulation
        this.simulatedFaces = [
            { id: 0, x: 180, y: 140, vx: 0.8, vy: 0.5, student: this.students[0], state: 'tracking', dwell: 0 },
            { id: 1, x: 380, y: 190, vx: -0.7, vy: 0.4, student: this.students[1], state: 'tracking', dwell: 0 },
            { id: 2, x: 260, y: 240, vx: 0.5, vy: -0.6, student: this.students[2], state: 'searching', dwell: 0 }
        ];

        this.startCanvasRender();
        this.startTelemetryLoop();
    },

    saveStudents() {
        try {
            localStorage.setItem('sim_students', JSON.stringify(this.students));
        } catch (e) { }
    },

    saveTeachers() {
        try {
            localStorage.setItem('sim_teachers', JSON.stringify(this.teachers));
        } catch (e) { }
    },

    saveRecords() {
        try {
            localStorage.setItem('sim_records', JSON.stringify(this.records));
        } catch (e) { }
    },

    startSession(teacherId = "TCH001", courseCode = "CS501", courseName = "AI & Computer Vision") {
        const teacher = this.teachers.find(t => t.teacher_id === teacherId) || this.teachers[0];
        this.session = {
            session_code: `SES-2026-${Math.floor(100 + Math.random() * 900)}`,
            teacher_id: teacher.teacher_id,
            teacher_name: teacher.name,
            course_code: courseCode,
            course_name: courseName,
            room_number: "Lecture Hall 101",
            start_time: new Date().toISOString(),
            is_active: 1
        };
        this.sessionStartTime = Date.now();
        App.updateSessionUI({ active: true, session: this.session, present_students_count: this.getPresentCount() });
        App.showToast(`▶ Lecture Started! Faculty: ${teacher.name}`, "success");
        AudioFx.playChime();
    },

    endSession() {
        this.session = null;
        this.sessionStartTime = null;
        App.updateSessionUI({ active: false, session: null, present_students_count: this.getPresentCount() });
        App.showToast("🛑 Lecture Session Ended (Face Attendance Gated)", "info");
        AudioFx.playBeep();
    },

    triggerFingerprintAuth(slot = 1) {
        AudioFx.playBeep();
        const teacher = this.teachers.find(t => t.fingerprint_id == slot) || this.teachers[0];

        if (this.session) {
            // End session
            this.endSession();
            return { authenticated: true, action: "END", message: `Session Ended by ${teacher.name}` };
        } else {
            // Start session
            this.startSession(teacher.teacher_id, "CS501", "AI & Computer Vision");
            return { authenticated: true, action: "START", message: `Fingerprint Verified: ${teacher.name}` };
        }
    },

    getPresentCount() {
        const presentIds = new Set(this.records.map(r => r.student_id));
        return presentIds.size;
    },

    markStudent(student) {
        const exists = this.records.some(r => r.student_id === student.student_id);
        const timestamp = new Date().toLocaleTimeString();
        const fullTime = new Date().toISOString().replace('T', ' ').substring(0, 19);

        const record = {
            id: this.records.length + 1,
            student_id: student.student_id,
            student_name: student.name,
            roll_number: student.roll_number,
            class_section: student.class_section,
            course_name: this.session ? this.session.course_name : "CS501",
            entry_time: fullTime,
            confidence: student.confidence || 0.95,
            status: "PRESENT"
        };

        this.records.unshift(record);
        this.saveRecords();

        App.addLiveAttendanceItem({
            student: {
                student_id: student.student_id,
                name: student.name,
                roll_number: student.roll_number,
                class_section: student.class_section,
                confidence: student.confidence || 0.95
            },
            timestamp: timestamp,
            is_new_entry: !exists
        });

        AudioFx.playChime();
        App.fetchAnalytics();
    },

    simulateWalkIn() {
        if (!this.session) {
            App.showToast("Cannot log attendance: Lecture is gated. Scan teacher fingerprint to begin.", "error");
            AudioFx.playBeep();
            return;
        }

        const unmarked = this.students.filter(s => !this.records.some(r => r.student_id === s.student_id));
        const candidate = unmarked.length > 0
            ? unmarked[Math.floor(Math.random() * unmarked.length)]
            : this.students[Math.floor(Math.random() * this.students.length)];

        if (candidate) {
            this.markStudent(candidate);
        }
    },

    async toggleWebcam() {
        const badgeLive = document.getElementById('badgeWebcamLive');
        const videoEl = document.getElementById('webcamVideo');

        if (this.useWebcam) {
            // Turn off
            this.useWebcam = false;
            if (this.webcamStream) {
                this.webcamStream.getTracks().forEach(t => t.stop());
                this.webcamStream = null;
            }
            if (badgeLive) badgeLive.style.display = 'none';
            document.getElementById('btnToggleWebcam').innerHTML = "📹 Use My Webcam";
            App.showToast("Switched back to AI Synthetic Classroom Feed", "info");
        } else {
            // Request camera
            try {
                const stream = await navigator.mediaDevices.getUserMedia({
                    video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
                    audio: false
                });
                this.webcamStream = stream;
                if (videoEl) {
                    videoEl.srcObject = stream;
                    await videoEl.play();
                }
                this.useWebcam = true;
                if (badgeLive) badgeLive.style.display = 'inline-block';
                document.getElementById('btnToggleWebcam').innerHTML = "⏹ Stop Webcam";
                App.showToast("Live browser webcam connected! Edge face detector active.", "success");
            } catch (err) {
                console.error("Webcam access error:", err);
                App.showToast("Camera access declined or unavailable: " + err.message, "error");
            }
        }
    },

    startCanvasRender() {
        const canvas = document.getElementById('liveCanvasFeed');
        const enrollCanvas = document.getElementById('enrollCanvasFeed');
        const videoEl = document.getElementById('webcamVideo');

        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const enrollCtx = enrollCanvas ? enrollCanvas.getContext('2d') : null;

        let frameCount = 0;

        const render = () => {
            frameCount++;
            const w = canvas.width;
            const h = canvas.height;

            if (this.useWebcam && videoEl && videoEl.readyState >= 2) {
                // Render from live webcam
                ctx.save();
                // Mirror horizontally for selfie webcam
                ctx.translate(w, 0);
                ctx.scale(-1, 1);
                ctx.drawImage(videoEl, 0, 0, w, h);
                ctx.restore();

                // Apply CLAHE / IR tint if active
                if (this.nightVision) {
                    ctx.fillStyle = "rgba(0, 240, 255, 0.08)";
                    ctx.fillRect(0, 0, w, h);
                }

                // Draw central face tracking box on user's face
                const faceBox = {
                    x: Math.round(w / 2 - 100 + Math.sin(frameCount * 0.05) * 8),
                    y: Math.round(h / 2 - 120 + Math.cos(frameCount * 0.04) * 6),
                    width: 200,
                    height: 240
                };

                this.drawFaceBox(ctx, faceBox, {
                    name: this.session ? "User (Local Webcam)" : "GATED - Teacher Auth Required",
                    confidence: 0.98,
                    dwell: "3.8s",
                    isGated: !this.session
                });
            } else {
                // Render high-tech synthetic edge camera stream
                this.renderSyntheticClassroom(ctx, w, h, frameCount);
            }

            // Sync frame to enrollment canvas if visible
            if (enrollCtx && enrollCanvas) {
                enrollCtx.drawImage(canvas, 0, 0, enrollCanvas.width, enrollCanvas.height);
            }

            // Auto-trigger simulated attendance periodically if session is active
            if (this.session && Date.now() - this.lastSimMarkTime > 6500) {
                const unmarked = this.students.filter(s => !this.records.some(r => r.student_id === s.student_id));
                if (unmarked.length > 0) {
                    const candidate = unmarked[Math.floor(Math.random() * unmarked.length)];
                    this.markStudent(candidate);
                    this.lastSimMarkTime = Date.now();
                }
            }

            this.animationFrameId = requestAnimationFrame(render);
        };

        render();
    },

    renderSyntheticClassroom(ctx, w, h, frameCount) {
        // Futuristic Classroom Background
        const grad = ctx.createLinearGradient(0, 0, 0, h);
        if (this.nightVision) {
            grad.addColorStop(0, "#031518");
            grad.addColorStop(1, "#020a0d");
        } else {
            grad.addColorStop(0, "#080e1b");
            grad.addColorStop(0.6, "#0c1527");
            grad.addColorStop(1, "#060912");
        }
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, w, h);

        // Perspective grid lines (Lab & classroom floor / ceiling)
        ctx.strokeStyle = this.nightVision ? "rgba(0, 240, 255, 0.07)" : "rgba(59, 130, 246, 0.08)";
        ctx.lineWidth = 1;

        for (let i = 0; i < w; i += 40) {
            ctx.beginPath();
            ctx.moveTo(i, 0);
            ctx.lineTo(w / 2 + (i - w / 2) * 1.5, h);
            ctx.stroke();
        }
        for (let j = 0; j < h; j += 35) {
            ctx.beginPath();
            ctx.moveTo(0, j);
            ctx.lineTo(w, j);
            ctx.stroke();
        }

        // Camera Angle & Lens Overlay
        ctx.fillStyle = this.nightVision ? "rgba(0, 240, 255, 0.03)" : "rgba(0, 240, 255, 0.02)";
        ctx.beginPath();
        ctx.arc(w / 2, h / 2, 220, 0, Math.PI * 2);
        ctx.fill();

        // Crosshairs in Center
        ctx.strokeStyle = "rgba(0, 240, 255, 0.25)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(w / 2 - 20, h / 2);
        ctx.lineTo(w / 2 + 20, h / 2);
        ctx.moveTo(w / 2, h / 2 - 20);
        ctx.lineTo(w / 2, h / 2 + 20);
        ctx.stroke();

        // Update & Render Moving Faces
        this.simulatedFaces.forEach((f, idx) => {
            f.x += f.vx;
            f.y += f.vy;
            if (f.x < 100 || f.x > w - 180) f.vx *= -1;
            if (f.y < 80 || f.y > h - 180) f.vy *= -1;

            const boxWidth = 90;
            const boxHeight = 110;

            // Draw stylized student silhouette
            ctx.fillStyle = this.nightVision ? "rgba(0, 240, 255, 0.12)" : "rgba(30, 58, 138, 0.2)";
            ctx.beginPath();
            ctx.ellipse(f.x + boxWidth / 2, f.y + 40, 30, 38, 0, 0, Math.PI * 2);
            ctx.fill();

            // Shoulders
            ctx.beginPath();
            ctx.ellipse(f.x + boxWidth / 2, f.y + 110, 48, 25, 0, 0, Math.PI);
            ctx.fill();

            // Face landmarks (eyes, nose, mouth)
            ctx.fillStyle = this.nightVision ? "#00f0ff" : "#38bdf8";
            const eyeY = f.y + 35 + Math.sin(frameCount * 0.08 + idx) * 1.5;
            ctx.beginPath();
            ctx.arc(f.x + 32, eyeY, 2.5, 0, Math.PI * 2);
            ctx.arc(f.x + 58, eyeY, 2.5, 0, Math.PI * 2);
            ctx.fill();

            // Nose
            ctx.beginPath();
            ctx.arc(f.x + 45, eyeY + 12, 1.8, 0, Math.PI * 2);
            ctx.fill();

            // Mouth
            ctx.strokeStyle = this.nightVision ? "#00f0ff" : "#38bdf8";
            ctx.beginPath();
            ctx.arc(f.x + 45, eyeY + 22, 8, 0.2, Math.PI - 0.2);
            ctx.stroke();

            // Draw Bounding Box & HUD Tags
            this.drawFaceBox(ctx, {
                x: f.x,
                y: f.y,
                width: boxWidth,
                height: boxHeight
            }, {
                name: this.session ? f.student.name : "GATED (Auth Req)",
                confidence: f.student.confidence,
                dwell: "4.1s",
                isGated: !this.session
            });
        });

        // Top HUD Watermark
        ctx.fillStyle = "rgba(0, 0, 0, 0.6)";
        ctx.fillRect(8, 8, 380, 24);
        ctx.fillStyle = "#38bdf8";
        ctx.font = "10px 'JetBrains Mono', monospace";
        ctx.fillText(
            `PI5_CAM0${this.cameraAngle} • YuNet-ONNX 128D • FPS:30 • ${this.nightVision ? 'IR:850nm' : 'RGB:AUTO'}`,
            14,
            24
        );
    },

    drawFaceBox(ctx, box, info) {
        const { x, y, width, height } = box;
        const color = info.isGated ? "#f59e0b" : "#10b981";

        // High-Tech Corner Brackets
        ctx.strokeStyle = color;
        ctx.lineWidth = 2.5;
        const corner = 16;

        // Top-Left
        ctx.beginPath();
        ctx.moveTo(x, y + corner);
        ctx.lineTo(x, y);
        ctx.lineTo(x + corner, y);
        ctx.stroke();

        // Top-Right
        ctx.beginPath();
        ctx.moveTo(x + width - corner, y);
        ctx.lineTo(x + width, y);
        ctx.lineTo(x + width, y + corner);
        ctx.stroke();

        // Bottom-Left
        ctx.beginPath();
        ctx.moveTo(x, y + height - corner);
        ctx.lineTo(x, y + height);
        ctx.lineTo(x + corner, y + height);
        ctx.stroke();

        // Bottom-Right
        ctx.beginPath();
        ctx.moveTo(x + width - corner, y + height);
        ctx.lineTo(x + width, y + height);
        ctx.lineTo(x + width, y + height - corner);
        ctx.stroke();

        // Box Glow
        ctx.fillStyle = info.isGated ? "rgba(245, 158, 11, 0.05)" : "rgba(16, 185, 129, 0.06)";
        ctx.fillRect(x, y, width, height);

        // Name Banner on Top
        ctx.fillStyle = color;
        ctx.fillRect(x, y - 22, width + 30, 20);

        ctx.fillStyle = "#000";
        ctx.font = "bold 10px 'Plus Jakarta Sans', sans-serif";
        ctx.fillText(info.name, x + 5, y - 8);

        // Subtext Pill below box
        ctx.fillStyle = "rgba(0,0,0,0.7)";
        ctx.fillRect(x, y + height + 4, width + 10, 16);
        ctx.fillStyle = color;
        ctx.font = "9px 'JetBrains Mono', monospace";
        ctx.fillText(`CONF: ${Math.round(info.confidence * 100)}% • IoU: 0.88`, x + 4, y + height + 16);
    },

    startTelemetryLoop() {
        // Fluctuate simulated Raspberry Pi 5 telemetry
        setInterval(() => {
            const temp = (48.2 + Math.random() * 1.8).toFixed(1);
            const cpu = (18 + Math.random() * 6).toFixed(1);
            const ram = (1380 + Math.random() * 90).toFixed(0);

            const setEl = (id, val) => {
                const el = document.getElementById(id);
                if (el) el.textContent = val;
            };

            setEl('diagTemp', `${temp}°C`);
            setEl('diagCpu', `${cpu}%`);
            setEl('diagRam', `${ram} MB / 4096 MB (35%)`);
            setEl('diagDisk', `24.5 GB Free`);
            setEl('diagFps', `30 FPS`);
            setEl('diagCamMode', this.useWebcam ? 'Browser WebRTC (Live Webcam)' : 'YuNet ONNX Pipeline (Synthetic)');
            setEl('diagFpMode', 'UART /dev/ttyAMA0 (Active Gating)');
            setEl('badgeCamFps', `30 FPS`);
        }, 2500);
    }
};

// Main UI Controller
const App = {
    isDemoMode: false,
    activeSession: null,
    sessionStartTime: null,
    timerInterval: null,
    presentStudents: new Set(),

    async init() {
        console.log("Initializing AI Attendance System...");
        this.bindEvents();
        this.initClock();

        // Check if backend API is reachable
        const isBackendAvailable = await this.testBackendConnection();

        if (isBackendAvailable) {
            console.log("Connected to native Raspberry Pi / FastAPI backend.");
            this.isDemoMode = false;
            this.setModeBadge("PI 5 HARDWARE CONNECTED", "#10b981");
            this.fetchSessionStatus();
            this.fetchAnalytics();
            this.fetchDiagnostics();
            this.fetchEnrolledStudents();
            this.connectWebSocket();
        } else {
            console.warn("Backend not detected. Initializing standalone GitHub Pages Demo Mode...");
            this.isDemoMode = true;
            this.setModeBadge("GITHUB PAGES DEMO", "#00f0ff");
            SimEngine.init();
            this.fetchEnrolledStudents();
            this.fetchAnalytics();
        }
    },

    async testBackendConnection() {
        if (window.location.protocol === 'file:' || window.location.hostname.includes('github.io')) {
            return false;
        }
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 1200);
            const res = await fetch('/api/session/status', { signal: controller.signal });
            clearTimeout(timeoutId);
            return res.ok;
        } catch (e) {
            return false;
        }
    },

    setModeBadge(text, color) {
        const pillText = document.getElementById('modePillText');
        const dot = document.getElementById('modeDot');
        if (pillText) pillText.textContent = text;
        if (dot) {
            dot.style.background = color;
            dot.style.boxShadow = `0 0 10px ${color}`;
        }
    },

    bindEvents() {
        // Tab Navigation
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const targetTab = btn.getAttribute('data-tab');
                this.switchTab(targetTab);
            });
        });

        // Fingerprint Scan Buttons
        const fpBtn = document.getElementById('btnFingerprintAuth');
        if (fpBtn) {
            fpBtn.addEventListener('click', () => this.triggerFingerprintScan(1));
        }
        const touchPrism = document.getElementById('touchPrism');
        if (touchPrism) {
            touchPrism.addEventListener('click', () => this.triggerFingerprintScan(1));
        }

        // Direct Start/End Lecture Button
        const toggleBtn = document.getElementById('btnToggleSession');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => this.toggleLectureSession());
        }

        // Camera Feed Controls
        const btnToggleCam = document.getElementById('btnToggleCam');
        if (btnToggleCam) {
            btnToggleCam.addEventListener('click', () => this.toggleCameraSource());
        }
        const btnToggleWebcam = document.getElementById('btnToggleWebcam');
        if (btnToggleWebcam) {
            btnToggleWebcam.addEventListener('click', () => SimEngine.toggleWebcam());
        }
        const btnSimulateFace = document.getElementById('btnSimulateFace');
        if (btnSimulateFace) {
            btnSimulateFace.addEventListener('click', () => SimEngine.simulateWalkIn());
        }

        // Enrollment Camera Controls
        const btnEnrollToggleCam = document.getElementById('btnEnrollToggleCam');
        if (btnEnrollToggleCam) {
            btnEnrollToggleCam.addEventListener('click', () => this.toggleCameraSource());
        }
        const btnLiveSnap = document.getElementById('btnLiveSnap');
        if (btnLiveSnap) {
            btnLiveSnap.addEventListener('click', () => this.handleLiveFaceSnap());
        }

        // Diagnostics Camera Buttons
        const btnDiagToggle = document.getElementById('btnDiagToggle');
        if (btnDiagToggle) btnDiagToggle.addEventListener('click', () => this.toggleCameraSource());
        const btnDiagCam0 = document.getElementById('btnDiagCam0');
        if (btnDiagCam0) btnDiagCam0.addEventListener('click', () => this.switchCameraTo(0));
        const btnDiagCam1 = document.getElementById('btnDiagCam1');
        if (btnDiagCam1) btnDiagCam1.addEventListener('click', () => this.switchCameraTo(1));

        // Roster buttons
        const btnRefresh = document.getElementById('btnRefreshStudents');
        if (btnRefresh) btnRefresh.addEventListener('click', () => this.fetchEnrolledStudents());
        const btnClear = document.getElementById('btnClearAllStudents');
        if (btnClear) btnClear.addEventListener('click', () => this.clearAllEnrolledStudents());

        // Student & Faculty Forms
        const studentForm = document.getElementById('studentEnrollForm');
        if (studentForm) studentForm.addEventListener('submit', (e) => this.handleStudentRegister(e));
        const teacherForm = document.getElementById('teacherEnrollForm');
        if (teacherForm) teacherForm.addEventListener('submit', (e) => this.handleTeacherRegister(e));

        // File upload preview
        const photoInput = document.getElementById('enrollPhotoFile');
        if (photoInput) {
            photoInput.addEventListener('change', (e) => {
                const file = e.target.files[0];
                if (file) {
                    const reader = new FileReader();
                    reader.onload = (re) => {
                        const previewImg = document.getElementById('enrollPhotoPreview');
                        const previewBox = document.getElementById('enrollPhotoPreviewBox');
                        const statusTxt = document.getElementById('previewStatusText');
                        if (previewImg) previewImg.src = re.target.result;
                        if (previewBox) previewBox.style.display = 'block';
                        if (statusTxt) statusTxt.textContent = `📁 File Selected: ${file.name}`;
                    };
                    reader.readAsDataURL(file);
                }
            });
        }

        // Export CSV Button
        const btnExport = document.getElementById('btnExportCsv');
        if (btnExport) {
            btnExport.addEventListener('click', () => this.handleExportCsv());
        }
    },

    switchTab(tabId) {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));

        const activeBtn = document.querySelector(`.tab-btn[data-tab="${tabId}"]`);
        const activePane = document.getElementById(tabId);
        if (activeBtn) activeBtn.classList.add('active');
        if (activePane) activePane.classList.add('active');

        if (tabId === 'tab-analytics') {
            this.fetchAnalytics();
            this.fetchRecordsTable();
        } else if (tabId === 'tab-enroll') {
            this.fetchEnrolledStudents();
        } else if (tabId === 'tab-diagnostics') {
            this.fetchDiagnostics();
        }
    },

    initClock() {
        const clockEl = document.getElementById('systemClock');
        const update = () => {
            const now = new Date();
            if (clockEl) {
                clockEl.textContent = now.toLocaleTimeString('en-US', { hour12: false });
            }
            if (this.sessionStartTime && this.activeSession) {
                const diffSec = Math.floor((Date.now() - this.sessionStartTime) / 1000);
                const m = String(Math.floor(diffSec / 60)).padStart(2, '0');
                const s = String(diffSec % 60).padStart(2, '0');
                const timerEl = document.getElementById('sessionTimer');
                if (timerEl) timerEl.textContent = `${m}:${s}`;
            }
        };
        setInterval(update, 1000);
        update();
    },

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/live`;

        try {
            this.ws = new WebSocket(wsUrl);
            this.ws.onopen = () => {
                console.log("WebSocket connected to live edge stream");
                this.showToast("Edge pipeline connected", "success");
            };
            this.ws.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    if (msg.type === "INITIAL_STATE") {
                        this.updateSessionUI(msg.payload);
                    } else if (msg.type === "STUDENT_MARKED") {
                        this.addLiveAttendanceItem(msg.payload);
                    } else if (msg.type === "SESSION_STARTED") {
                        this.showToast(`Lecture Session Started: ${msg.payload.course_name}`, "success");
                        this.fetchSessionStatus();
                    } else if (msg.type === "SESSION_ENDED") {
                        this.showToast(`Lecture Session Ended`, "info");
                        this.fetchSessionStatus();
                    }
                } catch (e) { }
            };
            this.ws.onclose = () => {
                setTimeout(() => {
                    if (!this.isDemoMode) this.connectWebSocket();
                }, 4000);
            };
        } catch (e) { }
    },

    async fetchSessionStatus() {
        if (this.isDemoMode) {
            this.updateSessionUI({
                active: !!SimEngine.session,
                session: SimEngine.session,
                present_students_count: SimEngine.getPresentCount()
            });
            return;
        }

        try {
            const res = await fetch('/api/session/status');
            const data = await res.json();
            this.updateSessionUI(data);
        } catch (e) { }
    },

    updateSessionUI(statusData) {
        const banner = document.getElementById('teacherBanner');
        const icon = document.getElementById('bannerIcon');
        const title = document.getElementById('bannerTitle');
        const sub = document.getElementById('bannerSub');
        const actionBtn = document.getElementById('btnFingerprintAuth');
        const sessPill = document.getElementById('sessionPill');
        const toggleBtn = document.getElementById('btnToggleSession');

        if (statusData.active && statusData.session) {
            this.activeSession = statusData.session;
            this.sessionStartTime = new Date(statusData.session.start_time).getTime();

            if (banner) banner.className = 'teacher-banner session-active';
            if (icon) icon.textContent = '👨‍🏫';
            if (title) title.textContent = `${statusData.session.course_name} (${statusData.session.course_code})`;
            if (sub) {
                sub.innerHTML = `Teacher: ${statusData.session.teacher_name} | Elapsed: <span id="sessionTimer" class="time-badge">00:00</span>`;
            }
            if (actionBtn) {
                actionBtn.className = 'fp-action-btn btn-stop';
                actionBtn.innerHTML = '<span>🛑</span> End Session (Fingerprint)';
            }
            if (sessPill) {
                sessPill.innerHTML = '<div class="pulse-dot"></div><span>SESSION ACTIVE</span>';
            }
            if (toggleBtn) {
                toggleBtn.style.background = 'linear-gradient(135deg, #e11d48, #be123c)';
                toggleBtn.innerHTML = '<span>⏹</span> End Lecture';
            }
        } else {
            this.activeSession = null;
            this.sessionStartTime = null;

            if (banner) banner.className = 'teacher-banner session-inactive';
            if (icon) icon.textContent = '🔒';
            if (title) title.textContent = 'Session Inactive (Attendance Logging Gated)';
            if (sub) sub.textContent = 'Teacher must authenticate via R307 fingerprint sensor to start lecture';

            if (actionBtn) {
                actionBtn.className = 'fp-action-btn';
                actionBtn.innerHTML = '<span>👆</span> Authenticate Teacher (R307)';
            }
            if (sessPill) {
                sessPill.innerHTML = '<div class="pulse-dot inactive"></div><span>GATED / INACTIVE</span>';
            }
            if (toggleBtn) {
                toggleBtn.style.background = 'linear-gradient(135deg, #10b981, #059669)';
                toggleBtn.innerHTML = '<span>▶</span> Start Lecture';
            }
        }

        const presentEl = document.getElementById('kpiPresentCount');
        if (presentEl && statusData.present_students_count !== undefined) {
            presentEl.textContent = statusData.present_students_count;
        }
    },

    async toggleLectureSession() {
        if (this.isDemoMode) {
            if (SimEngine.session) {
                SimEngine.endSession();
            } else {
                SimEngine.startSession();
            }
            return;
        }

        try {
            if (this.activeSession) {
                await fetch('/api/session/end', { method: 'POST' });
                this.showToast("🛑 Lecture Session Ended", "info");
            } else {
                await fetch('/api/session/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        teacher_id: "TCH001",
                        course_code: "CS501",
                        course_name: "AI & Computer Vision",
                        room_number: "Room 101"
                    })
                });
                this.showToast(`▶ Lecture Session Started!`, "success");
            }
            this.fetchSessionStatus();
        } catch (e) {
            this.showToast("Session toggle failed: " + e.message, "error");
        }
    },

    async triggerFingerprintScan(slot = 1) {
        const prism = document.getElementById('touchPrism');
        if (prism) prism.classList.add('scanning');

        if (this.isDemoMode) {
            setTimeout(() => {
                const res = SimEngine.triggerFingerprintAuth(slot);
                this.showToast(res.message, res.authenticated ? "success" : "error");
                if (prism) prism.classList.remove('scanning');
            }, 500);
            return;
        }

        try {
            this.showToast("R307 Sensor: Reading optical prism...", "info");
            const res = await fetch('/api/session/fingerprint/scan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ fingerprint_id: slot })
            });
            const data = await res.json();
            if (data.authenticated) {
                this.showToast(data.message, "success");
                this.fetchSessionStatus();
            } else {
                this.showToast(data.message || "Fingerprint not recognized", "error");
            }
        } catch (e) {
            this.showToast("Fingerprint scan error", "error");
        } finally {
            if (prism) prism.classList.remove('scanning');
        }
    },

    addLiveAttendanceItem(data) {
        const feed = document.getElementById('attendanceFeed');
        if (!feed) return;

        // Clear standby placeholder if present
        const placeholder = feed.querySelector('.feed-item[style*="opacity: 0.6"]');
        if (placeholder) placeholder.remove();

        const student = data.student;
        const timeStr = data.timestamp || new Date().toLocaleTimeString();

        this.presentStudents.add(student.student_id);
        const presentEl = document.getElementById('kpiPresentCount');
        if (presentEl) presentEl.textContent = this.presentStudents.size;

        const item = document.createElement('div');
        item.className = 'feed-item';
        item.innerHTML = `
            <div class="student-meta">
                <div class="student-avatar">${student.name.charAt(0)}</div>
                <div class="student-info">
                    <h4>${student.name}</h4>
                    <p>${student.roll_number} • ${student.class_section}</p>
                </div>
            </div>
            <div class="feed-badges">
                <div class="time-badge">${timeStr}</div>
                <div class="conf-pill">Match: ${Math.round((student.confidence || 0.95) * 100)}%</div>
            </div>
        `;

        feed.insertBefore(item, feed.firstChild);
        while (feed.children.length > 15) {
            feed.removeChild(feed.lastChild);
        }

        if (data.is_new_entry) {
            this.showToast(`✅ ${student.name} marked PRESENT`, "success");
        }
    },

    async fetchAnalytics() {
        if (this.isDemoMode) {
            const totalEnrolled = SimEngine.students.length;
            const presentCount = SimEngine.getPresentCount();
            const pct = totalEnrolled > 0 ? Math.round((presentCount / totalEnrolled) * 100) : 0;

            const enrolledEl = document.getElementById('kpiEnrolledCount');
            const rateEl = document.getElementById('kpiAttendanceRate');
            if (enrolledEl) enrolledEl.textContent = totalEnrolled;
            if (rateEl) rateEl.textContent = `${pct}%`;

            const mockAnalytics = {
                total_enrolled: totalEnrolled,
                attendance_percentage: pct,
                daily_trend: [
                    { date: 'Mon', count: Math.min(totalEnrolled, 6) },
                    { date: 'Tue', count: Math.min(totalEnrolled, 7) },
                    { date: 'Wed', count: Math.min(totalEnrolled, 8) },
                    { date: 'Thu', count: Math.min(totalEnrolled, 7) },
                    { date: 'Today', count: presentCount }
                ],
                weekly_trend: [
                    { week: 'Week 34', count: 7 },
                    { week: 'Week 35', count: 8 },
                    { week: 'Week 36', count: 7 },
                    { week: 'Week 37', count: presentCount || 8 }
                ]
            };

            if (typeof initCharts === 'function') {
                initCharts(mockAnalytics);
            }
            return;
        }

        try {
            const res = await fetch('/api/attendance/analytics');
            const data = await res.json();
            const enrolledEl = document.getElementById('kpiEnrolledCount');
            const rateEl = document.getElementById('kpiAttendanceRate');
            if (enrolledEl) enrolledEl.textContent = data.total_enrolled;
            if (rateEl) rateEl.textContent = `${data.attendance_percentage}%`;

            if (typeof initCharts === 'function') {
                initCharts(data);
            }
        } catch (e) { }
    },

    async fetchRecordsTable() {
        const tbody = document.getElementById('recordsTableBody');
        if (!tbody) return;

        if (this.isDemoMode) {
            tbody.innerHTML = '';
            if (SimEngine.records.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:#94a3b8;">No attendance records logged yet. Start lecture and simulate students!</td></tr>';
                return;
            }
            SimEngine.records.forEach(r => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${r.student_name}</strong></td>
                    <td>${r.roll_number}</td>
                    <td>${r.course_name || 'CS501'}</td>
                    <td>${r.entry_time.split(' ')[1] || r.entry_time}</td>
                    <td><span class="status-badge-present">PRESENT</span></td>
                    <td>${Math.round((r.confidence || 0.95) * 100)}%</td>
                `;
                tbody.appendChild(tr);
            });
            return;
        }

        try {
            const res = await fetch('/api/attendance/records');
            const data = await res.json();
            tbody.innerHTML = '';
            if (data.records.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:#94a3b8;">No attendance records found yet.</td></tr>';
                return;
            }
            data.records.forEach(r => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${r.student_name}</strong></td>
                    <td>${r.roll_number}</td>
                    <td>${r.course_name || 'CS501'}</td>
                    <td>${r.entry_time.split(' ')[1] || r.entry_time}</td>
                    <td><span class="status-badge-present">PRESENT</span></td>
                    <td>${Math.round(r.confidence * 100)}%</td>
                `;
                tbody.appendChild(tr);
            });
        } catch (e) { }
    },

    async fetchEnrolledStudents() {
        const tbody = document.getElementById('enrolledStudentsTableBody');
        if (!tbody) return;

        let studentsList = [];
        if (this.isDemoMode) {
            studentsList = SimEngine.students;
        } else {
            try {
                const res = await fetch('/api/enroll/students');
                const data = await res.json();
                studentsList = data.students || [];
            } catch (e) {
                studentsList = SimEngine.students;
            }
        }

        tbody.innerHTML = '';
        if (studentsList.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #94a3b8;">No enrolled students yet. Use the form above to enroll!</td></tr>';
            return;
        }

        studentsList.forEach(s => {
            const tr = document.createElement('tr');
            let photoHtml = '<div style="width: 38px; height: 38px; border-radius: 50%; background: #334155; display: flex; align-items: center; justify-content: center; font-size: 0.85rem; color: #94a3b8;">👤</div>';
            if (s.photo_preview || s.photo_path) {
                const src = s.photo_preview || `/faces/${s.photo_path.split('\\').pop().split('/').pop()}`;
                photoHtml = `<img src="${src}" style="width: 38px; height: 38px; border-radius: 50%; object-fit: cover; border: 2px solid #38bdf8;" alt="${s.name}" onerror="this.style.display='none'">`;
            }

            tr.innerHTML = `
                <td>${photoHtml}</td>
                <td><strong>${s.student_id}</strong></td>
                <td>${s.name}</td>
                <td>${s.roll_number}</td>
                <td>${s.class_section}</td>
                <td><span class="badge" style="background: rgba(16, 185, 129, 0.2); color: #10b981; border: 1px solid #10b981;">✓ 128D Enrolled</span></td>
                <td>
                    <button class="btn-ctrl" style="padding: 4px 8px; font-size: 0.72rem; color: #f87171;" onclick="App.deleteStudent('${s.student_id}')">Remove</button>
                </td>
            `;
            tbody.appendChild(tr);
        });

        const enrolledCountEl = document.getElementById('kpiEnrolledCount');
        if (enrolledCountEl) enrolledCountEl.textContent = studentsList.length;
    },

    deleteStudent(studentId) {
        if (this.isDemoMode) {
            SimEngine.students = SimEngine.students.filter(s => s.student_id !== studentId);
            SimEngine.saveStudents();
            this.fetchEnrolledStudents();
            this.showToast("Student removed from local directory", "info");
        } else {
            this.showToast("Delete operation available in system admin panel", "info");
        }
    },

    clearAllEnrolledStudents() {
        if (confirm("Are you sure you want to clear all enrolled students?")) {
            if (this.isDemoMode) {
                SimEngine.students = [];
                SimEngine.saveStudents();
                this.fetchEnrolledStudents();
                this.showToast("All student records cleared", "info");
            }
        }
    },

    async handleStudentRegister(e) {
        e.preventDefault();
        const studentId = document.getElementById('enrollStudentId').value.trim();
        const name = document.getElementById('enrollName').value.trim();
        const roll = document.getElementById('enrollRoll').value.trim();
        const section = document.getElementById('enrollSection').value.trim();
        const previewImg = document.getElementById('enrollPhotoPreview');

        if (this.isDemoMode) {
            const newStudent = {
                student_id: studentId,
                name: name,
                roll_number: roll,
                class_section: section,
                photo_preview: previewImg ? previewImg.src : null,
                confidence: 0.96
            };
            SimEngine.students.unshift(newStudent);
            SimEngine.saveStudents();
            this.showToast(`🎉 Enrolled ${name} (128D Embedding Created)!`, "success");
            AudioFx.playChime();
            this.fetchEnrolledStudents();
            document.getElementById('studentEnrollForm').reset();
            return;
        }

        try {
            const photoFile = document.getElementById('enrollPhotoFile').files[0];
            const formData = new FormData();
            formData.append('student_id', studentId);
            formData.append('name', name);
            formData.append('roll_number', roll);
            formData.append('class_section', section);
            if (photoFile) formData.append('file', photoFile);

            const res = await fetch('/api/enroll/face', { method: 'POST', body: formData });
            if (res.ok) {
                this.showToast(`✅ Successfully Enrolled ${name}!`, "success");
                this.fetchEnrolledStudents();
                document.getElementById('studentEnrollForm').reset();
            } else {
                throw new Error("Enrollment failed");
            }
        } catch (err) {
            this.showToast("Error registering student: " + err.message, "error");
        }
    },

    async handleTeacherRegister(e) {
        e.preventDefault();
        const teacherId = document.getElementById('enrollTeacherId').value.trim();
        const name = document.getElementById('enrollTeacherName').value.trim();
        const dept = document.getElementById('enrollTeacherDept').value.trim();
        const slot = parseInt(document.getElementById('enrollTeacherSlot').value.trim()) || 1;

        if (this.isDemoMode) {
            SimEngine.teachers.push({ teacher_id: teacherId, name: name, department: dept, fingerprint_id: slot });
            SimEngine.saveTeachers();
            this.showToast(`Faculty ${name} registered! Paired to R307 slot #${slot}`, "success");
            document.getElementById('teacherEnrollForm').reset();
            return;
        }

        try {
            const res = await fetch('/api/enroll/teacher', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ teacher_id: teacherId, name: name, department: dept, fingerprint_id: slot })
            });
            if (res.ok) {
                this.showToast(`✅ Faculty ${name} Registered!`, "success");
                document.getElementById('teacherEnrollForm').reset();
            }
        } catch (e) {
            this.showToast("Teacher enrollment error", "error");
        }
    },

    handleLiveFaceSnap() {
        const previewImg = document.getElementById('enrollPhotoPreview');
        const previewBox = document.getElementById('enrollPhotoPreviewBox');
        const statusTxt = document.getElementById('previewStatusText');
        const canvas = document.getElementById('liveCanvasFeed');

        if (canvas && previewImg) {
            // Grab current frame from live canvas
            const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
            previewImg.src = dataUrl;
            if (previewBox) previewBox.style.display = 'block';
            if (statusTxt) statusTxt.textContent = "📸 High-Resolution Face Frame Captured! Ready to Save.";
            AudioFx.playBeep();
            this.showToast("Face frame captured from live camera feed!", "info");
        }
    },

    toggleCameraSource() {
        if (this.isDemoMode) {
            SimEngine.cameraAngle = (SimEngine.cameraAngle + 1) % 2;
            SimEngine.nightVision = SimEngine.cameraAngle === 1;

            const badgeNight = document.getElementById('badgeNightVision');
            if (badgeNight) {
                badgeNight.textContent = SimEngine.nightVision ? "CLAHE IR 850nm" : "RGB DAYLIGHT";
                badgeNight.style.color = SimEngine.nightVision ? "#00f0ff" : "#10b981";
            }

            const diagCamSource = document.getElementById('diagCamSource');
            if (diagCamSource) diagCamSource.textContent = `Camera ${SimEngine.cameraAngle} (${SimEngine.nightVision ? 'IR Night-Vision' : 'Standard RGB'})`;

            this.showToast(`Switched to Camera Angle ${SimEngine.cameraAngle} (${SimEngine.nightVision ? 'IR Night Vision Active' : 'RGB Normal'})`, "info");
            return;
        }

        fetch('/api/diagnostics/camera/toggle', { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                this.showToast(`Camera switched to Device ${data.current_source}`, "success");
                this.fetchDiagnostics();
            })
            .catch(() => this.showToast("Camera switch unavailable", "error"));
    },

    switchCameraTo(src) {
        if (this.isDemoMode) {
            SimEngine.cameraAngle = src;
            SimEngine.nightVision = src === 1;
            this.showToast(`Activated Camera Device ${src}`, "info");
            return;
        }
        fetch('/api/diagnostics/camera/switch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ source: src })
        }).then(() => this.fetchDiagnostics());
    },

    async fetchDiagnostics() {
        if (this.isDemoMode) return;
        try {
            const res = await fetch('/api/diagnostics/system');
            const data = await res.json();
            const setVal = (id, val) => {
                const el = document.getElementById(id);
                if (el) el.textContent = val;
            };
            setVal('diagTemp', `${data.cpu_temp_c}°C`);
            setVal('diagCpu', `${data.cpu_usage_pct}%`);
            setVal('diagRam', `${data.ram_usage_mb} MB / ${data.ram_total_mb} MB (${data.ram_percent}%)`);
            setVal('diagDisk', `${data.disk_free_gb} GB Free`);
            setVal('diagFps', `${data.camera.fps} FPS`);
            setVal('diagCamMode', data.camera.is_synthetic ? 'Standby (Polling)' : 'V4L2 / CSI-2 (Hardware)');
            setVal('diagFpMode', `${data.fingerprint.mode} (${data.fingerprint.port})`);
            setVal('badgeCamFps', `${data.camera.fps} FPS`);
        } catch (e) { }
    },

    handleExportCsv() {
        if (this.isDemoMode) {
            let csvContent = "Student ID,Student Name,Roll Number,Course,Entry Time,Status,Confidence\n";
            if (SimEngine.records.length === 0) {
                // Export roster if no records yet
                SimEngine.students.forEach(s => {
                    csvContent += `${s.student_id},"${s.name}",${s.roll_number},CS501,${new Date().toLocaleTimeString()},PRESENT,0.95\n`;
                });
            } else {
                SimEngine.records.forEach(r => {
                    csvContent += `${r.student_id},"${r.student_name}",${r.roll_number},"${r.course_name || 'CS501'}",${r.entry_time},${r.status},${r.confidence}\n`;
                });
            }

            const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `attendance_export_${new Date().toISOString().slice(0, 10)}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            this.showToast("📥 Exported Attendance CSV Report!", "success");
            return;
        }

        window.open('/api/attendance/export/csv', '_blank');
    },

    showToast(message, type = 'info') {
        const container = document.getElementById('toastContainer');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        const icons = { success: '✅', error: '⚠️', info: 'ℹ️' };
        toast.innerHTML = `<span>${icons[type] || 'ℹ️'}</span><span>${message}</span>`;

        container.appendChild(toast);
        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease forwards';
            setTimeout(() => toast.remove(), 300);
        }, 3200);
    }
};

// Start application when DOM is ready
window.addEventListener('DOMContentLoaded', () => {
    App.init();
});
