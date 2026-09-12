/**
 * Real-Time Touchscreen Dashboard Application Controller
 * Handles WebSockets, REST APIs, Live Session Gating, and UI Interactions
 */

const App = {
    ws: null,
    activeSession: null,
    sessionStartTime: null,
    timerInterval: null,
    enrolledCount: 0,
    presentStudents: new Set(),
    webcamStream: null,
    useWebcam: false,

    getApiUrl(endpoint) {
        if (window.location.protocol !== 'file:' && window.location.port === '8080') {
            return endpoint;
        }
        const host = (window.location.hostname && window.location.hostname !== 'localhost') 
            ? window.location.hostname 
            : '127.0.0.1';
        return `http://${host}:8080${endpoint}`;
    },

    init() {
        console.log("Initializing AI Attendance System Dashboard (Production Mode)...");
        this.bindEvents();
        this.initClock();
        this.initFirebaseAuth();
        this.initVideoFeedWatchdog();
    },

    bindEvents() {
        // Tab Navigation
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const targetTab = btn.getAttribute('data-tab');
                this.switchTab(targetTab);
            });
        });

        // Direct Session Toggle (Start/End Lecture)
        const toggleBtn = document.getElementById('btnToggleSession');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => this.toggleLectureSession());
        }

        // Refresh & Clear Enrolled Students Buttons
        const btnRefreshStudents = document.getElementById('btnRefreshStudents');
        if (btnRefreshStudents) {
            btnRefreshStudents.addEventListener('click', () => this.fetchEnrolledStudents());
        }
        const btnClearAllStudents = document.getElementById('btnClearAllStudents');
        if (btnClearAllStudents) {
            btnClearAllStudents.addEventListener('click', () => this.clearAllEnrolledStudents());
        }

        // Camera Source Switchers & Webcam Toggle
        const btnToggleCam = document.getElementById('btnToggleCam');
        if (btnToggleCam) {
            btnToggleCam.addEventListener('click', () => this.toggleCameraSource());
        }
        const btnToggleWebcam = document.getElementById('btnToggleWebcam');
        if (btnToggleWebcam) {
            btnToggleWebcam.addEventListener('click', () => this.toggleWebcam());
        }
        const btnEnrollToggleCam = document.getElementById('btnEnrollToggleCam');
        if (btnEnrollToggleCam) {
            btnEnrollToggleCam.addEventListener('click', () => this.toggleCameraSource());
        }

        // Student Enrollment Form
        const studentForm = document.getElementById('studentEnrollForm');
        if (studentForm) {
            studentForm.addEventListener('submit', (e) => this.handleStudentRegister(e));
        }

        // Live Camera Face Capture Button
        const btnLiveSnap = document.getElementById('btnLiveSnap');
        if (btnLiveSnap) {
            btnLiveSnap.addEventListener('click', () => this.handleLiveFaceSnap());
        }

        // File input change preview
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
                        if (statusTxt) statusTxt.textContent = `📁 File Selected: ${file.name} (Click Save & Enroll)`;
                    };
                    reader.readAsDataURL(file);
                }
            });
        }

        // Export CSV Button
        const btnExport = document.getElementById('btnExportCsv');
        if (btnExport) {
            btnExport.addEventListener('click', () => {
                window.open(this.getApiUrl('/api/attendance/export/csv'), '_blank');
            });
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
            const camFeed = document.getElementById('enrollLiveCameraFeed');
            if (camFeed) camFeed.src = `${this.getApiUrl('/api/video/feed')}?t=` + Date.now();
        }
    },

    initFirebaseAuth() {
        const form = document.getElementById('firebaseAuthForm');
        const tabSignIn = document.getElementById('authTabSignIn');
        const tabRegister = document.getElementById('authTabRegister');
        const comingSoonBox = document.getElementById('registerComingSoonBox');
        const btnBackToSignIn = document.getElementById('btnBackToSignIn');
        const errorBanner = document.getElementById('authErrorBanner');
        const btnLogout = document.getElementById('btnLogout');
        const btnTogglePwd = document.getElementById('btnTogglePassword');
        const pwdInput = document.getElementById('authPassword');

        if (tabSignIn) {
            tabSignIn.addEventListener('click', () => {
                tabSignIn.classList.add('active');
                if (tabRegister) tabRegister.classList.remove('active');
                if (form) form.style.display = 'flex';
                if (comingSoonBox) comingSoonBox.style.display = 'none';
                if (errorBanner) errorBanner.style.display = 'none';
            });
        }

        if (tabRegister) {
            tabRegister.addEventListener('click', () => {
                tabRegister.classList.add('active');
                if (tabSignIn) tabSignIn.classList.remove('active');
                if (form) form.style.display = 'none';
                if (comingSoonBox) comingSoonBox.style.display = 'flex';
                if (errorBanner) errorBanner.style.display = 'none';
            });
        }

        if (btnBackToSignIn) {
            btnBackToSignIn.addEventListener('click', () => {
                if (tabSignIn) tabSignIn.click();
            });
        }

        if (btnTogglePwd && pwdInput) {
            btnTogglePwd.addEventListener('click', () => {
                const isPwd = pwdInput.type === 'password';
                pwdInput.type = isPwd ? 'text' : 'password';
                btnTogglePwd.innerHTML = isPwd ? '<i class="fa-regular fa-eye-slash"></i>' : '<i class="fa-regular fa-eye"></i>';
            });
        }

        if (form) {
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                const email = document.getElementById('authEmail').value.trim();
                const password = document.getElementById('authPassword').value;

                const spinner = document.getElementById('authSubmitSpinner');
                const submitBtn = document.getElementById('btnAuthSubmit');

                if (spinner) spinner.style.display = 'inline-block';
                if (submitBtn) submitBtn.disabled = true;
                if (errorBanner) errorBanner.style.display = 'none';

                try {
                    const bridge = window.FirebaseBridge;
                    if (!bridge) throw new Error("Firebase is connecting. Please retry in a moment.");

                    const res = await bridge.signIn(email, password);

                    if (res.success) {
                        this.showToast(`Welcome, ${res.user.displayName || res.user.email}!`, "success");
                        form.reset();
                    } else {
                        let msg = res.error || "Authentication failed.";
                        if (res.code === "auth/invalid-credential" || res.code === "auth/wrong-password" || res.code === "auth/user-not-found") {
                            msg = "Invalid email or password. Please contact administrator if you need login details.";
                        } else if (res.code === "auth/too-many-requests") {
                            msg = "Access temporarily blocked due to multiple failed attempts. Please try again later or contact administrator.";
                        } else if (res.code === "auth/operation-not-allowed") {
                            msg = "Email/Password sign-in is not enabled in Firebase Console. Please enable it under Authentication > Sign-in method.";
                        }
                        if (errorBanner) {
                            errorBanner.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> ${msg}`;
                            errorBanner.style.display = 'block';
                        }
                    }
                } catch (err) {
                    if (errorBanner) {
                        errorBanner.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> ${err.message}`;
                        errorBanner.style.display = 'block';
                    }
                } finally {
                    if (spinner) spinner.style.display = 'none';
                    if (submitBtn) submitBtn.disabled = false;
                }
            });
        }

        if (btnLogout) {
            btnLogout.addEventListener('click', async () => {
                if (window.FirebaseBridge) {
                    await window.FirebaseBridge.signOutUser();
                    this.showToast("Signed out of Firebase Cloud", "info");
                }
            });
        }

        const setupAuthListener = () => {
            if (window.FirebaseBridge) {
                window.FirebaseBridge.onAuthChange((user) => this.updateAuthUI(user));
            } else {
                window.addEventListener("firebase-bridge-ready", () => {
                    window.FirebaseBridge.onAuthChange((user) => this.updateAuthUI(user));
                }, { once: true });
            }
        };
        setupAuthListener();
    },

    updateAuthUI(user) {
        const gateway = document.getElementById('authGateway');
        const dashboard = document.getElementById('dashboardArea');
        const badge = document.getElementById('userAuthBadge');
        const emailSpan = document.getElementById('userEmailSpan');

        if (user) {
            console.log("Authenticated as:", user.email);
            if (gateway) gateway.style.display = 'none';
            if (dashboard) dashboard.style.display = 'flex';
            if (badge) badge.style.display = 'inline-flex';
            if (emailSpan) {
                emailSpan.textContent = user.displayName || user.email;
                emailSpan.title = user.email;
            }

            // Start live dashboard feeds
            this.refreshVideoFeeds();
            this.fetchSessionStatus();
            this.fetchAnalytics();
            this.fetchEnrolledStudents();
            if (!this.ws) {
                this.connectWebSocket();
            }
        } else {
            console.log("User unauthenticated - Gating dashboard.");
            if (dashboard) dashboard.style.display = 'none';
            if (gateway) gateway.style.display = 'flex';
            if (badge) badge.style.display = 'none';
        }
    },

    initClock() {
        const clockEl = document.getElementById('systemClock');
        const dateEl = document.getElementById('systemDate');
        const update = () => {
            const now = new Date();
            if (clockEl) {
                clockEl.textContent = now.toLocaleTimeString('en-US', { hour12: true, hour: '2-digit', minute: '2-digit', second: '2-digit' });
            }
            if (dateEl) {
                dateEl.textContent = now.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
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
        let wsUrl;
        if (window.location.protocol !== 'file:' && window.location.port === '8080') {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            wsUrl = `${protocol}//${window.location.host}/ws/live`;
        } else {
            const host = (window.location.hostname && window.location.hostname !== 'localhost')
                ? window.location.hostname
                : '127.0.0.1';
            wsUrl = `ws://${host}:8080/ws/live`;
        }

        try {
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                console.log("WebSocket connected to live edge stream");
                this.showToast("Edge pipeline connected", "success");
            };

            this.ws.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    this.handleWsMessage(msg);
                } catch (e) {
                    console.error("Error parsing WS message:", e);
                }
            };

            this.ws.onclose = () => {
                console.warn("WebSocket disconnected. Reconnecting in 3s...");
                setTimeout(() => this.connectWebSocket(), 3000);
            };
        } catch (e) {
            console.error("WebSocket connection error:", e);
        }
    },

    handleWsMessage(msg) {
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
    },

    async fetchSessionStatus() {
        try {
            const res = await fetch(this.getApiUrl('/api/session/status'));
            const data = await res.json();
            this.updateSessionUI(data);
        } catch (e) {
            console.error("Error fetching session status:", e);
        }
    },

    updateSessionUI(statusData) {
        const banner = document.getElementById('teacherBanner');
        const icon = document.getElementById('bannerIcon');
        const title = document.getElementById('bannerTitle');
        const sub = document.getElementById('bannerSub');
        const sessPill = document.getElementById('sessionPill');

        if (statusData.active && statusData.session) {
            this.activeSession = statusData.session;
            this.sessionStartTime = new Date(statusData.session.start_time).getTime();

            if (banner) banner.className = 'teacher-banner session-active';
            if (icon) icon.innerHTML = '<i class="fa-solid fa-chalkboard-user"></i>';
            if (title) title.textContent = `${statusData.session.course_name} (${statusData.session.course_code})`;
            if (sub) {
                sub.textContent = `Teacher: ${statusData.session.teacher_name} | Elapsed: `;
                const timerSpan = document.createElement('span');
                timerSpan.id = 'sessionTimer';
                timerSpan.className = 'time-badge';
                timerSpan.textContent = '00:00';
                sub.appendChild(timerSpan);
            }

            if (sessPill) {
                sessPill.innerHTML = '<div class="pulse-dot"></div><span>SESSION ACTIVE</span>';
            }
        } else {
            this.activeSession = null;
            this.sessionStartTime = null;

            if (banner) banner.className = 'teacher-banner session-inactive';
            if (icon) icon.innerHTML = '<i class="fa-solid fa-lock"></i>';
            if (title) title.textContent = 'Lecture Session Inactive';
            if (sub) sub.textContent = 'Click "Start Lecture" to begin recording live face attendance';

            if (sessPill) {
                sessPill.innerHTML = '<div class="pulse-dot inactive"></div><span>GATED / INACTIVE</span>';
            }
        }

        // Update Start / End Lecture button
        const toggleBtn = document.getElementById('btnToggleSession');
        if (toggleBtn) {
            if (statusData.active && statusData.session) {
                toggleBtn.style.background = 'linear-gradient(135deg, #e11d48, #be123c)';
                toggleBtn.innerHTML = '<i class="fa-solid fa-stop"></i> End Lecture';
            } else {
                toggleBtn.style.background = 'linear-gradient(135deg, #10b981, #059669)';
                toggleBtn.innerHTML = '<i class="fa-solid fa-play"></i> Start Lecture';
            }
        }

        // Update Counter
        const presentEl = document.getElementById('kpiPresentCount');
        if (presentEl && statusData.present_students_count !== undefined) {
            presentEl.textContent = statusData.present_students_count;
        }
    },

    async toggleLectureSession() {
        const toggleBtn = document.getElementById('btnToggleSession');
        if (toggleBtn) toggleBtn.disabled = true;

        try {
            // First check status from backend to ensure state accuracy
            const statusCheck = await fetch(this.getApiUrl('/api/session/status')).catch(() => null);
            let isAlreadyActive = false;
            if (statusCheck && statusCheck.ok) {
                const sData = await statusCheck.json().catch(() => ({}));
                this.updateSessionUI(sData);
                isAlreadyActive = !!sData.active;
            } else if (this.activeSession) {
                isAlreadyActive = true;
            }

            if (isAlreadyActive) {
                const res = await fetch(this.getApiUrl('/api/session/end'), { method: 'POST' });
                if (res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.showToast("Lecture Session Ended", "info");
                    if (window.FirebaseBridge && data.session) {
                        window.FirebaseBridge.syncSession(data.session);
                    }
                } else {
                    const errData = await res.json().catch(() => ({}));
                    this.showToast(errData.detail || "Could not end session", "error");
                }
            } else {
                let teacherId = "FACULTY-01";
                let teacherName = "Faculty Member";

                try {
                    const teachersRes = await fetch(this.getApiUrl('/api/enroll/teachers'));
                    if (teachersRes.ok) {
                        const teachersData = await teachersRes.json();
                        if (teachersData.teachers && teachersData.teachers.length > 0) {
                            teacherId = teachersData.teachers[0].teacher_id;
                            teacherName = teachersData.teachers[0].name;
                        }
                    }
                } catch (te) {
                    console.warn("Could not pre-fetch faculty roster:", te);
                }

                const res = await fetch(this.getApiUrl('/api/session/start'), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        teacher_id: teacherId,
                        course_code: "CS501",
                        course_name: "Embedded AI & Edge Systems",
                        room_number: "Room 101"
                    })
                });

                if (!res.ok) {
                    const errData = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
                    throw new Error(errData.detail || errData.message || `Server error (${res.status})`);
                }

                const data = await res.json();
                const faculty = data.session?.teacher_name || teacherName;
                this.showToast(`Lecture Session Started! Faculty: ${faculty}`, "success");
                if (window.FirebaseBridge && data.session) {
                    window.FirebaseBridge.syncSession(data.session);
                }
            }
            await this.fetchSessionStatus();
        } catch (e) {
            console.error("Error toggling session:", e);
            if (e.message && (e.message.includes("Failed to fetch") || e.message.includes("NetworkError"))) {
                this.showToast("Backend offline! Please ensure 'python run.py' is running on http://127.0.0.1:8080", "error");
            } else {
                this.showToast("Session error: " + e.message, "error");
            }
        } finally {
            if (toggleBtn) toggleBtn.disabled = false;
        }
    },



    addLiveAttendanceItem(data) {
        const feed = document.getElementById('attendanceFeed');
        if (!feed) return;

        // Clear empty state prompt if present
        const emptyState = document.getElementById('feedEmptyState');
        if (emptyState) emptyState.remove();

        const student = data.student;
        const timeStr = data.timestamp || new Date().toLocaleTimeString();

        // Increment present count
        this.presentStudents.add(student.student_id);
        const presentEl = document.getElementById('kpiPresentCount');
        if (presentEl) presentEl.textContent = this.presentStudents.size;

        // Create item element
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
                <div class="conf-pill">Match: ${Math.round(student.confidence * 100)}%</div>
            </div>
        `;

        // Prepend to feed
        feed.insertBefore(item, feed.firstChild);

        // Limit feed to top 15 items
        while (feed.children.length > 15) {
            feed.removeChild(feed.lastChild);
        }

        // Real-Time Cloud Sync to Firebase Firestore
        if (window.FirebaseBridge) {
            window.FirebaseBridge.syncAttendanceRecord({
                student_id: student.student_id,
                student_name: student.name,
                session_id: this.activeSession?.id || null,
                session_code: this.activeSession?.session_code || "",
                confidence: student.confidence || 0.95,
                timestamp: data.timestamp || new Date().toISOString()
            });
        }

        if (data.is_new_entry) {
            this.showToast(`${student.name} marked PRESENT`, "success");
        }
    },

    async fetchAnalytics() {
        try {
            const res = await fetch(this.getApiUrl('/api/attendance/analytics'));
            const data = await res.json();

            // Update KPI cards
            const enrolledEl = document.getElementById('kpiEnrolledCount');
            const rateEl = document.getElementById('kpiAttendanceRate');

            if (enrolledEl) enrolledEl.textContent = data.total_enrolled;
            if (rateEl) rateEl.textContent = `${data.attendance_percentage}%`;

            // Initialize charts
            if (typeof initCharts === 'function') {
                initCharts(data);
            }
        } catch (e) {
            console.error("Error fetching analytics:", e);
        }
    },

    async fetchRecordsTable() {
        const tbody = document.getElementById('recordsTableBody');
        if (!tbody) return;

        try {
            const res = await fetch(this.getApiUrl('/api/attendance/records'));
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
        } catch (e) {
            console.error("Error fetching records table:", e);
        }
    },

    async toggleCameraSource() {
        const btns = [
            document.getElementById('btnToggleCam'),
            document.getElementById('btnEnrollToggleCam')
        ].filter(Boolean);

        btns.forEach(b => {
            b.disabled = true;
            b.dataset.origText = b.innerHTML;
            b.innerHTML = "⏳ Switching...";
        });

        try {
            const res = await fetch(this.getApiUrl('/api/diagnostics/camera/toggle'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await res.json();

            if (res.ok && data.success) {
                const dev = data.current_source !== undefined ? data.current_source : 0;
                this.showToast(`🎥 Camera Switched to Device ${dev}`, "success");
                this.updateCameraSourceUI(dev);
                this.refreshVideoFeeds();
            } else {
                this.showToast(data.message || data.detail || "Unable to switch camera", "error");
            }
        } catch (e) {
            console.error("Error toggling camera feed:", e);
            this.showToast("Camera toggle error: " + e.message, "error");
        } finally {
            btns.forEach(b => {
                b.disabled = false;
            });
        }
    },

    async switchCameraTo(targetSrc) {
        const btns = [
            document.getElementById('btnToggleCam'),
            document.getElementById('btnEnrollToggleCam'),
            document.getElementById('btnDiagToggle'),
            document.getElementById('btnDiagCam0'),
            document.getElementById('btnDiagCam1')
        ].filter(Boolean);

        btns.forEach(b => {
            b.disabled = true;
        });

        try {
            const res = await fetch(this.getApiUrl('/api/diagnostics/camera/switch'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source: targetSrc })
            });
            const data = await res.json();

            if (res.ok && data.success) {
                this.showToast(`🎥 Activated Camera Device ${targetSrc}`, "success");
                this.updateCameraSourceUI(targetSrc);
                this.refreshVideoFeeds();
            } else {
                this.showToast(data.message || data.detail || `Camera ${targetSrc} unavailable`, "error");
            }
        } catch (e) {
            console.error("Error activating camera:", e);
            this.showToast("Camera activation error: " + e.message, "error");
        } finally {
            btns.forEach(b => {
                b.disabled = false;
            });
        }
    },

    updateCameraSourceUI(currentDev) {
        const nextDev = currentDev === 0 ? 1 : 0;
        const btnToggleCam = document.getElementById('btnToggleCam');
        if (btnToggleCam) btnToggleCam.innerHTML = `<i class="fa-solid fa-arrows-rotate"></i> Switch to Cam ${nextDev}`;

        const btnEnrollToggleCam = document.getElementById('btnEnrollToggleCam');
        if (btnEnrollToggleCam) btnEnrollToggleCam.innerHTML = `<i class="fa-solid fa-arrows-rotate"></i> Switch (Cam ${nextDev})`;

        const diagCamSource = document.getElementById('diagCamSource');
        if (diagCamSource) diagCamSource.textContent = `Camera ${currentDev} (Active)`;
    },

    refreshVideoFeeds() {
        const t = Date.now();
        const liveImg = document.getElementById('liveVideoFeed');
        if (liveImg && !this.useWebcam) {
            liveImg.src = `${this.getApiUrl('/api/video/feed')}?t=${t}`;
        }
        const enrollLiveImg = document.getElementById('enrollLiveCameraFeed');
        if (enrollLiveImg) {
            enrollLiveImg.src = `${this.getApiUrl('/api/video/feed')}?t=${t}`;
        }
    },

    async handleStudentRegister(e) {
        e.preventDefault();
        const studentId = document.getElementById('enrollStudentId').value.trim();
        const name = document.getElementById('enrollName').value.trim();
        const roll = document.getElementById('enrollRoll').value.trim();
        const section = document.getElementById('enrollSection').value.trim();
        const photoFile = document.getElementById('enrollPhotoFile').files[0];

        try {
            if (photoFile) {
                // Upload face photo directly with student metadata
                const formData = new FormData();
                formData.append('student_id', studentId);
                formData.append('name', name);
                formData.append('roll_number', roll);
                formData.append('class_section', section);
                formData.append('file', photoFile);

                const faceRes = await fetch(this.getApiUrl('/api/enroll/face'), {
                    method: 'POST',
                    body: formData
                });
                const faceData = await faceRes.json();
                if (!faceRes.ok) throw new Error(faceData.detail || "Failed to upload and enroll photo");

                // Sync Student Profile & Thumbnail to Cloud Firestore (100% Free)
                if (window.FirebaseBridge) {
                    window.FirebaseBridge.syncStudentProfile({
                        student_id: studentId,
                        name: name,
                        roll_number: roll,
                        class_section: section,
                        photo_preview: faceData.photo_preview || ""
                    });
                }

                const previewImg = document.getElementById('enrollPhotoPreview');
                const previewBox = document.getElementById('enrollPhotoPreviewBox');
                const statusTxt = document.getElementById('previewStatusText');
                if (faceData.photo_preview && previewImg) previewImg.src = faceData.photo_preview;
                if (previewBox) previewBox.style.display = 'block';
                if (statusTxt) statusTxt.innerHTML = `<i class="fa-solid fa-circle-check"></i> Photo Enrolled for ${name}! (Cloud Synced)`;

                this.showToast(`Successfully registered & enrolled face for ${name}!`, "success");
            } else {
                // Register student record without photo
                const res = await fetch(this.getApiUrl('/api/enroll/student'), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        student_id: studentId,
                        name: name,
                        roll_number: roll,
                        class_section: section
                    })
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || "Failed to register student");

                if (window.FirebaseBridge) {
                    window.FirebaseBridge.syncStudentProfile({
                        student_id: studentId,
                        name: name,
                        roll_number: roll,
                        class_section: section,
                        photo_url: ""
                    });
                }

                this.showToast(`Registered student profile for ${name}`, "success");
            }

            document.getElementById('studentEnrollForm').reset();
            this.fetchEnrolledStudents();
            this.fetchAnalytics();
        } catch (e) {
            console.error("Student enroll error:", e);
            this.showToast("Enrollment failed: " + e.message, "error");
        }
    },

    async handleTeacherRegister(e) {
        e.preventDefault();
        const teacherId = document.getElementById('enrollTeacherId').value.trim();
        const name = document.getElementById('enrollTeacherName').value.trim();
        const dept = document.getElementById('enrollTeacherDept').value.trim();
        const slot = parseInt(document.getElementById('enrollTeacherSlot').value);

        try {
            const res = await fetch(this.getApiUrl('/api/enroll/teacher'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    teacher_id: teacherId,
                    name: name,
                    department: dept,
                    fingerprint_id: slot
                })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "Failed to register faculty member");

            this.showToast(`Registered Faculty: ${name} (Fingerprint Slot #${slot})`, "success");
            document.getElementById('teacherEnrollForm').reset();
            this.fetchSessionStatus();
        } catch (err) {
            this.showToast("Faculty registration failed: " + err.message, "error");
        }
    },

    async handleLiveFaceSnap() {
        const studentId = document.getElementById('enrollStudentId').value.trim();
        const name = document.getElementById('enrollName').value.trim();
        const roll = document.getElementById('enrollRoll').value.trim();
        const section = document.getElementById('enrollSection').value.trim();

        if (!studentId || !name || !roll || !section) {
            this.showToast("Please fill in Student ID, Full Name, Roll, and Section before snapping photo", "error");
            return;
        }

        const snapBtn = document.getElementById('btnLiveSnap');
        if (snapBtn) {
            snapBtn.disabled = true;
            snapBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Snapping & Detecting Face...';
        }

        try {
            let res;
            if (this.useWebcam && this.webcamStream) {
                // Grab frame from browser webcam video element
                const videoEl = document.getElementById('webcamVideo');
                const canvas = document.createElement('canvas');
                canvas.width = videoEl.videoWidth || 640;
                canvas.height = videoEl.videoHeight || 480;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height);
                const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.95));

                const formData = new FormData();
                formData.append('student_id', studentId);
                formData.append('name', name);
                formData.append('roll_number', roll);
                formData.append('class_section', section);
                formData.append('file', blob, 'webcam_snap.jpg');

                res = await fetch(this.getApiUrl('/api/enroll/face'), {
                    method: 'POST',
                    body: formData
                });
            } else {
                // Trigger snap on edge hardware camera
                res = await fetch(this.getApiUrl('/api/enroll/snap'), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        student_id: studentId,
                        name: name,
                        roll_number: roll,
                        class_section: section
                    })
                });
            }

            const data = await res.json();

            if (res.ok && data.success) {
                const previewImg = document.getElementById('enrollPhotoPreview');
                const previewBox = document.getElementById('enrollPhotoPreviewBox');
                const statusTxt = document.getElementById('previewStatusText');

                if (data.photo_preview && previewImg) {
                    previewImg.src = data.photo_preview;
                }
                if (previewBox) {
                    previewBox.style.display = 'block';
                }
                if (statusTxt) {
                    const detectMsg = data.faces_detected > 0 ? `(${data.faces_detected} face detected & boxed)` : "(Face vector generated)";
                    statusTxt.innerHTML = `<i class="fa-solid fa-circle-check"></i> Photo Captured & Enrolled for ${data.name || studentId}! ${detectMsg}`;
                }

                // Real-Time Cloud Sync to Firestore (100% Free)
                if (window.FirebaseBridge) {
                    window.FirebaseBridge.syncStudentProfile({
                        student_id: studentId,
                        name: name || data.name || studentId,
                        roll_number: roll,
                        class_section: section,
                        photo_preview: data.photo_preview || ""
                    });
                }

                this.showToast(`Captured & Enrolled photo for ${data.name || studentId}!`, "success");
                this.fetchEnrolledStudents();
                this.fetchAnalytics();
            } else {
                this.showToast(data.detail || data.message || "Capture failed. Make sure your face is visible to camera.", "error");
            }
        } catch (e) {
            console.error("Live snap error:", e);
            this.showToast("Face capture error: " + e.message, "error");
        } finally {
            if (snapBtn) {
                snapBtn.disabled = false;
                snapBtn.innerHTML = '<i class="fa-solid fa-camera"></i> SNAP & ENROLL FACE';
            }
        }
    },

    async fetchEnrolledStudents() {
        const tbody = document.getElementById('enrolledStudentsTableBody');
        if (!tbody) return;

        try {
            const res = await fetch(this.getApiUrl('/api/enroll/students'));
            const data = await res.json();
            const students = data.students || [];

            tbody.innerHTML = '';
            if (students.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: #94a3b8; padding: 20px;">No enrolled students found. Use the form above to enroll.</td></tr>';
                return;
            }

            students.forEach(s => {
                const tr = document.createElement('tr');
                const photoSrc = s.photo_path ? `${this.getApiUrl('/faces/' + s.photo_path.split('\\\\').pop().split('/').pop())}?t=${Date.now()}` : '';
                const photoHtml = photoSrc 
                    ? `<img src="${photoSrc}" style="width: 38px; height: 38px; border-radius: 6px; object-fit: cover; border: 1px solid rgba(79, 70, 229, 0.3);" onerror="this.outerHTML='<div style=\\'width:38px;height:38px;border-radius:6px;background:#f1f5f9;border:1px solid #e2e8f0;display:flex;align-items:center;justify-content:center;color:#64748b;\\'><i class=\\'fa-solid fa-user\\'></i></div>'">`
                    : `<div style="width: 38px; height: 38px; border-radius: 6px; background: #f1f5f9; border: 1px solid #e2e8f0; display: flex; align-items: center; justify-content: center; color: #64748b;"><i class="fa-solid fa-user"></i></div>`;
                
                const hasVector = s.embeddings_count && s.embeddings_count > 0;
                const statusBadge = hasVector 
                    ? `<span style="display: inline-block; padding: 3px 8px; border-radius: 12px; background: rgba(16, 185, 129, 0.15); color: #10b981; font-weight: 700; font-size: 0.72rem; border: 1px solid rgba(16, 185, 129, 0.3);"><i class="fa-solid fa-check"></i> 128D ACTIVE</span>`
                    : `<span style="display: inline-block; padding: 3px 8px; border-radius: 12px; background: rgba(245, 158, 11, 0.15); color: #f59e0b; font-weight: 700; font-size: 0.72rem; border: 1px solid rgba(245, 158, 11, 0.3);">PENDING PHOTO</span>`;

                tr.innerHTML = `
                    <td>${photoHtml}</td>
                    <td><strong>${s.student_id}</strong></td>
                    <td>${s.name}</td>
                    <td>${s.roll_number}</td>
                    <td>${s.class_section}</td>
                    <td>${statusBadge}</td>
                    <td>
                        <button class="btn-ctrl" onclick="App.deleteStudent('${s.student_id}', '${(s.name || s.student_id).replace(/'/g, "\\'")}')" style="padding: 4px 10px; font-size: 0.72rem; background: rgba(239, 68, 68, 0.1); color: #ef4444; border-color: rgba(239, 68, 68, 0.3);">
                            <i class="fa-solid fa-trash-can"></i> Delete
                        </button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        } catch (e) {
            console.error("Error fetching enrolled students:", e);
            tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: #ef4444;">Failed to load roster.</td></tr>';
        }
    },

    async deleteStudent(studentId, studentName) {
        if (!confirm(`Are you sure you want to delete student "${studentName || studentId}" and their face biometric data?`)) {
            return;
        }

        try {
            const res = await fetch(this.getApiUrl(`/api/enroll/student/${encodeURIComponent(studentId)}`), {
                method: 'DELETE'
            });
            const data = await res.json();
            if (res.ok && data.success) {
                this.showToast(`🗑️ Deleted student: ${studentName || studentId}`, "info");
                this.fetchEnrolledStudents();
                this.fetchAnalytics();
                this.fetchRecordsTable();
            } else {
                this.showToast(data.detail || "Failed to delete student", "error");
            }
        } catch (err) {
            console.error("Error deleting student:", err);
            this.showToast("Delete error: " + err.message, "error");
        }
    },

    async clearAllEnrolledStudents() {
        if (!confirm("Are you sure you want to delete ALL enrolled students and biometric face data? This cannot be undone.")) {
            return;
        }

        try {
            const res = await fetch(this.getApiUrl('/api/enroll/students/all'), {
                method: 'DELETE'
            });
            const data = await res.json();
            if (res.ok && data.success) {
                this.showToast("All enrolled student biometric data deleted", "success");
                this.fetchEnrolledStudents();
                this.fetchAnalytics();
                this.fetchRecordsTable();
            } else {
                this.showToast(data.detail || "Failed to delete all students", "error");
            }
        } catch (err) {
            console.error("Error deleting all students:", err);
            this.showToast("Delete error: " + err.message, "error");
        }
    },

    async toggleWebcam() {
        const videoEl = document.getElementById('webcamVideo');
        const imgEl = document.getElementById('liveVideoFeed');
        const badge = document.getElementById('badgeWebcamLive');
        const btn = document.getElementById('btnToggleWebcam');

        if (this.useWebcam) {
            if (this.webcamStream) {
                this.webcamStream.getTracks().forEach(t => t.stop());
                this.webcamStream = null;
            }
            if (videoEl) videoEl.style.display = 'none';
            if (imgEl) imgEl.style.display = 'block';
            if (badge) badge.style.display = 'none';
            if (btn) btn.innerHTML = '<i class="fa-solid fa-camera"></i> Browser Webcam';
            this.useWebcam = false;
            this.showToast("Switched back to Edge Camera stream", "info");
        } else {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({
                    video: { width: { ideal: 640 }, height: { ideal: 480 } }
                });
                this.webcamStream = stream;
                if (videoEl) {
                    videoEl.srcObject = stream;
                    videoEl.style.display = 'block';
                }
                if (imgEl) imgEl.style.display = 'none';
                if (badge) badge.style.display = 'inline-block';
                if (btn) btn.innerHTML = '<i class="fa-solid fa-arrows-rotate"></i> Edge Camera Stream';
                this.useWebcam = true;
                this.showToast("Connected to browser live webcam!", "success");
            } catch (err) {
                console.error("Webcam access error:", err);
                this.showToast("Could not access browser webcam: " + err.message, "error");
            }
        }
    },

    initVideoFeedWatchdog() {
        const img = document.getElementById('liveVideoFeed');
        if (!img) return;

        img.onerror = () => {
            const statusBadge = document.getElementById('badgeCamStatus');
            if (statusBadge) {
                statusBadge.textContent = "STANDBY / CONNECTING";
                statusBadge.style.color = "#f59e0b";
            }
            setTimeout(() => {
                img.src = `${this.getApiUrl('/api/video/feed')}?t=${Date.now()}`;
            }, 2500);
        };

        img.onload = () => {
            const statusBadge = document.getElementById('badgeCamStatus');
            if (statusBadge) {
                statusBadge.textContent = "LIVE STREAM";
                statusBadge.style.color = "#10b981";
            }
        };
    },

    showToast(message, type = "info") {
        const container = document.getElementById('toastContainer');
        if (!container) return;

        const iconHtml = type === 'success' 
            ? '<i class="fa-solid fa-circle-check" style="color: var(--accent-green); font-size: 1.1rem;"></i>' 
            : (type === 'error' 
                ? '<i class="fa-solid fa-triangle-exclamation" style="color: var(--accent-rose); font-size: 1.1rem;"></i>' 
                : '<i class="fa-solid fa-circle-info" style="color: var(--accent-indigo); font-size: 1.1rem;"></i>');

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `${iconHtml}<span>${message}</span>`;
        container.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 3500);
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
