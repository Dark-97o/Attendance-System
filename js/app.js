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
    enrollWebcamStream: null,
    useEnrollWebcam: false,
    enrollMode: 'student',
    isResettingPassword: false,
    selectedClassFilter: 'ALL',
    cachedStudentsList: [],
    cachedTeachersList: [],
    timetableRoutines: [],
    timetableMonitorInterval: null,
    emailjsConfig: {
        serviceId: '',
        templateId: '',
        publicKey: ''
    },

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
        this.initClassFilters();
        this.initTimetableMonitor();
        this.initEmailJS();
        this.fetchTodayAttendance();
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

        // Enrollment Mode Switcher (Student vs Teacher vs Timetable)
        const btnModeStudent = document.getElementById('btnModeStudent');
        const btnModeTeacher = document.getElementById('btnModeTeacher');
        const btnModeTimetable = document.getElementById('btnModeTimetable');
        const studentForm = document.getElementById('studentEnrollForm');
        const teacherForm = document.getElementById('teacherEnrollForm');
        const timetableManagerBox = document.getElementById('timetableManagerBox');
        const cameraAndFormsRow = document.getElementById('enrollCameraAndFormsRow');
        const btnLiveSnap = document.getElementById('btnLiveSnap');

        if (btnModeStudent && btnModeTeacher) {
            btnModeStudent.addEventListener('click', () => {
                this.enrollMode = 'student';
                btnModeStudent.classList.add('active');
                btnModeTeacher.classList.remove('active');
                if (btnModeTimetable) btnModeTimetable.classList.remove('active');
                if (cameraAndFormsRow) cameraAndFormsRow.style.display = 'grid';
                if (timetableManagerBox) timetableManagerBox.style.display = 'none';
                if (studentForm) studentForm.style.display = 'block';
                if (teacherForm) teacherForm.style.display = 'none';
                if (btnLiveSnap) btnLiveSnap.innerHTML = '<i class="fa-solid fa-camera"></i> SNAP & ENROLL STUDENT FACE';
            });

            btnModeTeacher.addEventListener('click', () => {
                this.enrollMode = 'teacher';
                btnModeTeacher.classList.add('active');
                btnModeStudent.classList.remove('active');
                if (btnModeTimetable) btnModeTimetable.classList.remove('active');
                if (cameraAndFormsRow) cameraAndFormsRow.style.display = 'grid';
                if (timetableManagerBox) timetableManagerBox.style.display = 'none';
                if (studentForm) studentForm.style.display = 'none';
                if (teacherForm) teacherForm.style.display = 'block';
                if (btnLiveSnap) btnLiveSnap.innerHTML = '<i class="fa-solid fa-camera"></i> SNAP & ENROLL TEACHER FACE';
            });

            if (btnModeTimetable) {
                btnModeTimetable.addEventListener('click', () => {
                    this.enrollMode = 'timetable';
                    btnModeTimetable.classList.add('active');
                    btnModeStudent.classList.remove('active');
                    btnModeTeacher.classList.remove('active');
                    if (cameraAndFormsRow) cameraAndFormsRow.style.display = 'none';
                    if (timetableManagerBox) timetableManagerBox.style.display = 'block';
                    this.fetchTimetableRoutines();
                    this.populateTeacherDropdownForRoutine();
                });
            }
        }

        // Desired Camera Switcher Dropdown in Enrollment Studio
        const enrollCameraSelect = document.getElementById('enrollCameraSelect');
        if (enrollCameraSelect) {
            enrollCameraSelect.addEventListener('change', (e) => {
                const selected = e.target.value;
                this.switchEnrollCamera(selected);
            });
        }

        const btnEnrollToggleCam = document.getElementById('btnEnrollToggleCam');
        if (btnEnrollToggleCam) {
            btnEnrollToggleCam.addEventListener('click', () => {
                if (!enrollCameraSelect) {
                    this.toggleCameraSource();
                    return;
                }
                const opts = Array.from(enrollCameraSelect.options).map(o => o.value);
                const curIdx = opts.indexOf(enrollCameraSelect.value);
                const nextVal = opts[(curIdx + 1) % opts.length];
                enrollCameraSelect.value = nextVal;
                this.switchEnrollCamera(nextVal);
            });
        }

        // Roster Directory Toggles (Students vs Teachers)
        const btnShowStudentRoster = document.getElementById('btnShowStudentRoster');
        const btnShowTeacherRoster = document.getElementById('btnShowTeacherRoster');
        const studentsTableWrapper = document.getElementById('studentsTableWrapper');
        const teachersTableWrapper = document.getElementById('teachersTableWrapper');

        if (btnShowStudentRoster && btnShowTeacherRoster) {
            btnShowStudentRoster.addEventListener('click', () => {
                btnShowStudentRoster.classList.add('active');
                btnShowTeacherRoster.classList.remove('active');
                if (studentsTableWrapper) studentsTableWrapper.style.display = 'block';
                if (teachersTableWrapper) teachersTableWrapper.style.display = 'none';
                this.fetchEnrolledStudents();
            });

            btnShowTeacherRoster.addEventListener('click', () => {
                btnShowTeacherRoster.classList.add('active');
                btnShowStudentRoster.classList.remove('active');
                if (studentsTableWrapper) studentsTableWrapper.style.display = 'none';
                if (teachersTableWrapper) teachersTableWrapper.style.display = 'block';
                this.fetchEnrolledTeachers();
            });
        }

        // Refresh & Clear Enrolled Students / Roster Buttons
        const btnRefreshStudents = document.getElementById('btnRefreshStudents');
        if (btnRefreshStudents) {
            btnRefreshStudents.addEventListener('click', () => this.fetchEnrolledStudents());
        }
        const btnRefreshRoster = document.getElementById('btnRefreshRoster');
        if (btnRefreshRoster) {
            btnRefreshRoster.addEventListener('click', () => {
                if (btnShowTeacherRoster && btnShowTeacherRoster.classList.contains('active')) {
                    this.fetchEnrolledTeachers();
                } else {
                    this.fetchEnrolledStudents();
                }
            });
        }
        const btnClearAllStudents = document.getElementById('btnClearAllStudents');
        if (btnClearAllStudents) {
            btnClearAllStudents.addEventListener('click', () => this.clearAllEnrolledStudents());
        }

        // Main Live Camera Source Switchers & Webcam Toggle
        const btnToggleCam = document.getElementById('btnToggleCam');
        if (btnToggleCam) {
            btnToggleCam.addEventListener('click', () => this.toggleCameraSource());
        }
        const btnToggleWebcam = document.getElementById('btnToggleWebcam');
        if (btnToggleWebcam) {
            btnToggleWebcam.addEventListener('click', () => this.toggleWebcam());
        }

        // Student Enrollment Form Submission
        if (studentForm) {
            studentForm.addEventListener('submit', (e) => this.handleStudentRegister(e));
        }

        // Teacher Enrollment Form Submission
        if (teacherForm) {
            teacherForm.addEventListener('submit', (e) => this.handleTeacherRegister(e));
        }

        // Live Camera Face Capture Button
        if (btnLiveSnap) {
            btnLiveSnap.addEventListener('click', () => this.handleLiveFaceSnap());
        }

        // Student File input change preview
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
                        if (statusTxt) statusTxt.textContent = `📁 Student File Selected: ${file.name} (Click Save & Upload)`;
                    };
                    reader.readAsDataURL(file);
                }
            });
        }

        // Teacher File input change preview
        const teacherPhotoInput = document.getElementById('enrollTeacherPhotoFile');
        if (teacherPhotoInput) {
            teacherPhotoInput.addEventListener('change', (e) => {
                const file = e.target.files[0];
                if (file) {
                    const reader = new FileReader();
                    reader.onload = (re) => {
                        const previewImg = document.getElementById('enrollPhotoPreview');
                        const previewBox = document.getElementById('enrollPhotoPreviewBox');
                        const statusTxt = document.getElementById('previewStatusText');
                        if (previewImg) previewImg.src = re.target.result;
                        if (previewBox) previewBox.style.display = 'block';
                        if (statusTxt) statusTxt.textContent = `📁 Faculty Photo: ${file.name} (Click Save Faculty Details)`;
                    };
                    reader.readAsDataURL(file);
                }
            });
        }

        // Timetable Period Form Submission
        const timetableForm = document.getElementById('timetableForm');
        if (timetableForm) {
            timetableForm.addEventListener('submit', (e) => this.handleRoutineSubmit(e));
        }

        // Timetable CSV Dropzone & File Input
        const routineDropZone = document.getElementById('routineDropZone');
        const routineFileInput = document.getElementById('routineFileInput');
        if (routineDropZone && routineFileInput) {
            routineDropZone.addEventListener('click', () => routineFileInput.click());
            routineDropZone.addEventListener('dragover', (e) => {
                e.preventDefault();
                routineDropZone.style.borderColor = 'var(--accent-indigo)';
                routineDropZone.style.background = '#eef2ff';
            });
            routineDropZone.addEventListener('dragleave', () => {
                routineDropZone.style.borderColor = '#cbd5e1';
                routineDropZone.style.background = '#f8fafc';
            });
            routineDropZone.addEventListener('drop', (e) => {
                e.preventDefault();
                routineDropZone.style.borderColor = '#cbd5e1';
                routineDropZone.style.background = '#f8fafc';
                const files = e.dataTransfer.files;
                if (files && files.length > 0) {
                    this.handleRoutineUpload(files[0]);
                }
            });
            routineFileInput.addEventListener('change', (e) => {
                const file = e.target.files[0];
                if (file) {
                    this.handleRoutineUpload(file);
                    routineFileInput.value = '';
                }
            });
        }

        // Sample CSV Download & Clear Timetable Buttons
        const btnDownloadSampleCsv = document.getElementById('btnDownloadSampleCsv');
        if (btnDownloadSampleCsv) {
            btnDownloadSampleCsv.addEventListener('click', () => this.downloadSampleCsv());
        }

        const btnClearAllRoutines = document.getElementById('btnClearAllRoutines');
        if (btnClearAllRoutines) {
            btnClearAllRoutines.addEventListener('click', () => this.clearAllTimetableRoutines());
        }

        // Routine Table Filters
        const filterRoutineDay = document.getElementById('filterRoutineDay');
        const filterRoutineClass = document.getElementById('filterRoutineClass');
        const btnRefreshTimetable = document.getElementById('btnRefreshTimetable');
        if (filterRoutineDay) {
            filterRoutineDay.addEventListener('change', () => this.renderTimetableRoutines());
        }
        if (filterRoutineClass) {
            filterRoutineClass.addEventListener('change', () => this.renderTimetableRoutines());
        }
        if (btnRefreshTimetable) {
            btnRefreshTimetable.addEventListener('click', () => this.fetchTimetableRoutines());
        }

        // EmailJS Daily Summary Modal Controls
        const btnOpenEmailModal = document.getElementById('btnOpenEmailModal');
        const btnCloseEmailModal = document.getElementById('btnCloseEmailModal');
        const emailModal = document.getElementById('emailModal');
        const btnSaveEmailjsConfig = document.getElementById('btnSaveEmailjsConfig');
        const btnTestEmailPreview = document.getElementById('btnTestEmailPreview');
        const btnDispatchDailyEmails = document.getElementById('btnDispatchDailyEmails');

        if (btnOpenEmailModal && emailModal) {
            btnOpenEmailModal.addEventListener('click', () => {
                emailModal.style.display = 'flex';
                this.updateEmailRecipientCount();
            });
        }
        if (btnCloseEmailModal && emailModal) {
            btnCloseEmailModal.addEventListener('click', () => {
                emailModal.style.display = 'none';
            });
        }
        if (btnSaveEmailjsConfig) {
            btnSaveEmailjsConfig.addEventListener('click', () => this.saveEmailjsConfig());
        }
        if (btnTestEmailPreview) {
            btnTestEmailPreview.addEventListener('click', () => this.previewDailyEmailSummary());
        }
        if (btnDispatchDailyEmails) {
            btnDispatchDailyEmails.addEventListener('click', () => this.dispatchDailyAttendanceEmails());
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
            this.fetchEnrolledTeachers();
            const camFeed = document.getElementById('enrollLiveCameraFeed');
            if (camFeed && !this.useEnrollWebcam) camFeed.src = `${this.getApiUrl('/api/video/feed')}?t=` + Date.now();
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
        const btnForgotPassword = document.getElementById('btnForgotPassword');
        const forgotPasswordBox = document.getElementById('forgotPasswordBox');
        const forgotPasswordForm = document.getElementById('forgotPasswordForm');
        const resetEmailInput = document.getElementById('resetEmail');
        const resetErrorBanner = document.getElementById('resetErrorBanner');
        const resetSuccessBanner = document.getElementById('resetSuccessBanner');
        const btnBackFromReset = document.getElementById('btnBackFromReset');

        const returnToSignIn = () => {
            this.isResettingPassword = false;
            if (tabSignIn) tabSignIn.click();
        };

        if (tabSignIn) {
            tabSignIn.addEventListener('click', () => {
                this.isResettingPassword = false;
                tabSignIn.classList.add('active');
                if (tabRegister) tabRegister.classList.remove('active');
                if (form) form.style.display = 'flex';
                if (comingSoonBox) comingSoonBox.style.display = 'none';
                if (forgotPasswordBox) forgotPasswordBox.style.display = 'none';
                if (errorBanner) errorBanner.style.display = 'none';
            });
        }

        if (tabRegister) {
            tabRegister.addEventListener('click', () => {
                this.isResettingPassword = false;
                tabRegister.classList.add('active');
                if (tabSignIn) tabSignIn.classList.remove('active');
                if (form) form.style.display = 'none';
                if (comingSoonBox) comingSoonBox.style.display = 'flex';
                if (forgotPasswordBox) forgotPasswordBox.style.display = 'none';
                if (errorBanner) errorBanner.style.display = 'none';
            });
        }

        if (btnBackToSignIn) {
            btnBackToSignIn.addEventListener('click', returnToSignIn);
        }

        if (btnForgotPassword) {
            btnForgotPassword.addEventListener('click', async () => {
                this.isResettingPassword = true;
                if (form) form.style.display = 'none';
                if (comingSoonBox) comingSoonBox.style.display = 'none';
                if (forgotPasswordBox) forgotPasswordBox.style.display = 'flex';
                if (tabSignIn) tabSignIn.classList.remove('active');
                if (tabRegister) tabRegister.classList.remove('active');
                if (resetErrorBanner) resetErrorBanner.style.display = 'none';
                if (resetSuccessBanner) resetSuccessBanner.style.display = 'none';

                // Pre-fill email if user already entered it in sign-in form
                const typedEmail = document.getElementById('authEmail')?.value.trim();
                if (typedEmail && resetEmailInput) {
                    resetEmailInput.value = typedEmail;
                }
                if (resetEmailInput) resetEmailInput.focus();

                // Explicitly purge any lingering user session so the user is strictly logged out
                if (window.FirebaseBridge) {
                    try {
                        await window.FirebaseBridge.signOutUser();
                    } catch (e) {
                        // ignore
                    }
                }
            });
        }

        if (btnBackFromReset) {
            btnBackFromReset.addEventListener('click', returnToSignIn);
        }

        if (forgotPasswordForm) {
            forgotPasswordForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.isResettingPassword = true;

                const email = resetEmailInput ? resetEmailInput.value.trim() : '';
                if (!email) return;

                const spinner = document.getElementById('resetSubmitSpinner');
                const submitBtn = document.getElementById('btnSubmitReset');

                if (spinner) spinner.style.display = 'inline-block';
                if (submitBtn) submitBtn.disabled = true;
                if (resetErrorBanner) resetErrorBanner.style.display = 'none';
                if (resetSuccessBanner) resetSuccessBanner.style.display = 'none';

                try {
                    const bridge = window.FirebaseBridge;
                    if (!bridge) throw new Error("Firebase is connecting. Please retry in a moment.");

                    // Purge any active auth session before and after reset dispatch
                    await bridge.signOutUser().catch(() => {});

                    const res = await bridge.resetPassword(email);

                    // Re-enforce signed out status
                    await bridge.signOutUser().catch(() => {});

                    if (res.success) {
                        if (resetSuccessBanner) {
                            resetSuccessBanner.innerHTML = `
                                <div style="display: flex; flex-direction: column; gap: 10px;">
                                    <div style="display: flex; gap: 8px; align-items: flex-start;">
                                        <i class="fa-solid fa-circle-check" style="font-size: 1.1rem; color: #16a34a; margin-top: 2px;"></i>
                                        <div>
                                            <strong>Password Reset Link Sent!</strong>
                                            <div style="font-size: 0.78rem; margin-top: 4px; color: #166534; line-height: 1.45;">
                                                We've sent a secure reset link to <strong>${email}</strong>.<br>
                                                Please check your email, complete password reset, then return to sign in with your new password.
                                            </div>
                                        </div>
                                    </div>
                                    <button type="button" class="btn-submit" id="btnResetDoneSignIn" style="margin-top: 4px; padding: 10px; font-size: 0.84rem; background: var(--accent-indigo); width: 100%;">
                                        <i class="fa-solid fa-arrow-right-to-bracket"></i> Return to Faculty Sign In
                                    </button>
                                </div>
                            `;
                            resetSuccessBanner.style.display = 'block';

                            const doneBtn = document.getElementById('btnResetDoneSignIn');
                            if (doneBtn) {
                                doneBtn.addEventListener('click', returnToSignIn);
                            }
                        }
                        this.showToast("Password reset link dispatched to your email!", "success");
                    } else {
                        let msg = res.error || "Unable to send password reset email.";
                        if (res.code === "auth/user-not-found") {
                            msg = "No registered faculty account found with this institutional email address.";
                        } else if (res.code === "auth/invalid-email") {
                            msg = "Please enter a valid email address.";
                        } else if (res.code === "auth/too-many-requests") {
                            msg = "Too many attempts. Please wait a few moments before trying again.";
                        }
                        if (resetErrorBanner) {
                            resetErrorBanner.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> ${msg}`;
                            resetErrorBanner.style.display = 'block';
                        }
                    }
                } catch (err) {
                    if (resetErrorBanner) {
                        resetErrorBanner.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> ${err.message}`;
                        resetErrorBanner.style.display = 'block';
                    }
                } finally {
                    if (spinner) spinner.style.display = 'none';
                    if (submitBtn) submitBtn.disabled = false;

                    // Hard security guarantee: ensure dashboard remains hidden
                    const dashboard = document.getElementById('dashboardArea');
                    const gateway = document.getElementById('authGateway');
                    if (dashboard) dashboard.style.display = 'none';
                    if (gateway) gateway.style.display = 'flex';
                }
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

        // Security check: if the user is in the middle of password reset, never show dashboard
        if (this.isResettingPassword) {
            console.log("[Auth Gateway] In password reset mode - suppressing dashboard access.");
            if (dashboard) dashboard.style.display = 'none';
            if (gateway) gateway.style.display = 'flex';
            if (badge) badge.style.display = 'none';
            return;
        }

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
        this.renderLiveClassPresence();

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

        const enrollCameraSelect = document.getElementById('enrollCameraSelect');
        if (enrollCameraSelect && enrollCameraSelect.value !== 'webcam') {
            enrollCameraSelect.value = String(currentDev);
        }
        const statusText = document.getElementById('enrollCamStatusText');
        if (statusText && !this.useEnrollWebcam) statusText.textContent = `CAMERA ${currentDev} (LIVE)`;
    },

    async switchEnrollCamera(camVal) {
        const videoEl = document.getElementById('enrollWebcamVideo');
        const imgEl = document.getElementById('enrollLiveCameraFeed');
        const statusText = document.getElementById('enrollCamStatusText');
        const statusDot = document.getElementById('enrollCamStatusDot');

        if (camVal === 'webcam') {
            try {
                if (!this.enrollWebcamStream) {
                    const stream = await navigator.mediaDevices.getUserMedia({
                        video: { width: { ideal: 640 }, height: { ideal: 480 } }
                    });
                    this.enrollWebcamStream = stream;
                }
                if (videoEl) {
                    videoEl.srcObject = this.enrollWebcamStream;
                    videoEl.style.display = 'block';
                }
                if (imgEl) imgEl.style.display = 'none';
                if (statusText) statusText.textContent = "BROWSER WEBCAM (LIVE)";
                if (statusDot) statusDot.style.background = "#38bdf8";
                this.useEnrollWebcam = true;
                this.showToast("Switched to Browser Live Webcam for Enrollment", "info");
            } catch (err) {
                console.error("Enrollment webcam error:", err);
                this.showToast("Could not access browser webcam: " + err.message, "error");
                const sel = document.getElementById('enrollCameraSelect');
                if (sel) sel.value = "0";
                this.switchEnrollCamera("0");
            }
        } else {
            // Hardware Edge Camera 0, 1, or 2
            if (this.enrollWebcamStream) {
                this.enrollWebcamStream.getTracks().forEach(t => t.stop());
                this.enrollWebcamStream = null;
            }
            if (videoEl) videoEl.style.display = 'none';
            if (imgEl) imgEl.style.display = 'block';
            if (statusDot) statusDot.style.background = "#10b981";
            if (statusText) statusText.textContent = `CAMERA ${camVal} (LIVE)`;
            this.useEnrollWebcam = false;

            const camIdx = parseInt(camVal);
            if (!isNaN(camIdx)) {
                await this.switchCameraTo(camIdx);
            }
        }
    },

    refreshVideoFeeds() {
        const t = Date.now();
        const liveImg = document.getElementById('liveVideoFeed');
        if (liveImg && !this.useWebcam) {
            liveImg.src = `${this.getApiUrl('/api/video/feed')}?t=${t}`;
        }
        const enrollLiveImg = document.getElementById('enrollLiveCameraFeed');
        if (enrollLiveImg && !this.useEnrollWebcam) {
            enrollLiveImg.src = `${this.getApiUrl('/api/video/feed')}?t=${t}`;
        }
    },

    async handleStudentRegister(e) {
        e.preventDefault();
        const studentId = document.getElementById('enrollStudentId').value.trim();
        const name = document.getElementById('enrollName').value.trim();
        const roll = document.getElementById('enrollRoll').value.trim();
        const section = document.getElementById('enrollSection').value.trim();
        const email = document.getElementById('enrollEmail') ? document.getElementById('enrollEmail').value.trim() : '';
        const photoFile = document.getElementById('enrollPhotoFile').files[0];

        try {
            if (photoFile) {
                // Upload face photo directly with student metadata
                const formData = new FormData();
                formData.append('student_id', studentId);
                formData.append('name', name);
                formData.append('roll_number', roll);
                formData.append('class_section', section);
                formData.append('email', email);
                formData.append('entity_type', 'student');
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
                        email: email,
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
                        class_section: section,
                        email: email
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
                        email: email,
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
        const slotVal = document.getElementById('enrollTeacherSlot').value.trim();
        const slot = slotVal ? parseInt(slotVal) : null;
        const photoFile = document.getElementById('enrollTeacherPhotoFile').files[0];

        try {
            if (photoFile) {
                const formData = new FormData();
                formData.append('teacher_id', teacherId);
                formData.append('name', name);
                formData.append('department', dept);
                if (slot !== null) formData.append('fingerprint_id', slot);
                formData.append('entity_type', 'teacher');
                formData.append('file', photoFile);

                const faceRes = await fetch(this.getApiUrl('/api/enroll/face'), {
                    method: 'POST',
                    body: formData
                });
                const faceData = await faceRes.json();
                if (!faceRes.ok) throw new Error(faceData.detail || "Failed to upload faculty photo");

                const previewImg = document.getElementById('enrollPhotoPreview');
                const previewBox = document.getElementById('enrollPhotoPreviewBox');
                const statusTxt = document.getElementById('previewStatusText');
                if (faceData.photo_preview && previewImg) previewImg.src = faceData.photo_preview;
                if (previewBox) previewBox.style.display = 'block';
                if (statusTxt) statusTxt.innerHTML = `<i class="fa-solid fa-circle-check"></i> Faculty Photo Enrolled for ${name}!`;

                this.showToast(`Successfully registered Faculty ${name} with face!`, "success");
            } else {
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

                this.showToast(`Registered Faculty: ${name} (${dept})`, "success");
            }

            document.getElementById('teacherEnrollForm').reset();
            this.fetchEnrolledTeachers();
            this.fetchSessionStatus();
        } catch (err) {
            this.showToast("Faculty registration failed: " + err.message, "error");
        }
    },

    async handleLiveFaceSnap() {
        const snapBtn = document.getElementById('btnLiveSnap');

        if (this.enrollMode === 'student') {
            const studentId = document.getElementById('enrollStudentId').value.trim();
            const name = document.getElementById('enrollName').value.trim();
            const roll = document.getElementById('enrollRoll').value.trim();
            const section = document.getElementById('enrollSection').value.trim();
            const email = document.getElementById('enrollEmail') ? document.getElementById('enrollEmail').value.trim() : '';

            if (!studentId || !name || !roll || !section) {
                this.showToast("Please fill in Student Name, ID Number, Roll Number, and Class before snapping photo", "error");
                return;
            }

            if (snapBtn) {
                snapBtn.disabled = true;
                snapBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Snapping & Detecting Student Face...';
            }

            try {
                let res;
                if (this.useEnrollWebcam && this.enrollWebcamStream) {
                    // Grab frame from browser enrollment webcam video element
                    const videoEl = document.getElementById('enrollWebcamVideo');
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
                    formData.append('email', email);
                    formData.append('entity_type', 'student');
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
                            class_section: section,
                            email: email,
                            entity_type: 'student'
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
                        statusTxt.innerHTML = `<i class="fa-solid fa-circle-check"></i> Student Photo Enrolled for ${data.name || studentId}! ${detectMsg}`;
                    }

                    // Real-Time Cloud Sync to Firestore (100% Free)
                    if (window.FirebaseBridge) {
                        window.FirebaseBridge.syncStudentProfile({
                            student_id: studentId,
                            name: name || data.name || studentId,
                            roll_number: roll,
                            class_section: section,
                            email: email,
                            photo_preview: data.photo_preview || ""
                        });
                    }

                    this.showToast(`Captured & Enrolled face for student ${data.name || studentId}!`, "success");
                    this.fetchEnrolledStudents();
                    this.fetchAnalytics();
                } else {
                    this.showToast(data.detail || data.message || "Capture failed. Make sure face is visible to camera.", "error");
                }
            } catch (e) {
                console.error("Live student snap error:", e);
                this.showToast("Face capture error: " + e.message, "error");
            } finally {
                if (snapBtn) {
                    snapBtn.disabled = false;
                    snapBtn.innerHTML = '<i class="fa-solid fa-camera"></i> SNAP & ENROLL STUDENT FACE';
                }
            }
        } else {
            // Teacher Face Capture
            const teacherId = document.getElementById('enrollTeacherId').value.trim();
            const name = document.getElementById('enrollTeacherName').value.trim();
            const dept = document.getElementById('enrollTeacherDept').value.trim();
            const slotVal = document.getElementById('enrollTeacherSlot').value.trim();
            const slot = slotVal ? parseInt(slotVal) : null;

            if (!teacherId || !name || !dept) {
                this.showToast("Please fill in Teacher ID, Full Name, and Department before snapping photo", "error");
                return;
            }

            if (snapBtn) {
                snapBtn.disabled = true;
                snapBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Snapping & Detecting Faculty Face...';
            }

            try {
                let res;
                if (this.useEnrollWebcam && this.enrollWebcamStream) {
                    const videoEl = document.getElementById('enrollWebcamVideo');
                    const canvas = document.createElement('canvas');
                    canvas.width = videoEl.videoWidth || 640;
                    canvas.height = videoEl.videoHeight || 480;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height);
                    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.95));

                    const formData = new FormData();
                    formData.append('teacher_id', teacherId);
                    formData.append('name', name);
                    formData.append('department', dept);
                    if (slot !== null) formData.append('fingerprint_id', slot);
                    formData.append('entity_type', 'teacher');
                    formData.append('file', blob, 'teacher_webcam_snap.jpg');

                    res = await fetch(this.getApiUrl('/api/enroll/face'), {
                        method: 'POST',
                        body: formData
                    });
                } else {
                    res = await fetch(this.getApiUrl('/api/enroll/snap'), {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            teacher_id: teacherId,
                            name: name,
                            department: dept,
                            fingerprint_id: slot,
                            entity_type: 'teacher'
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
                        statusTxt.innerHTML = `<i class="fa-solid fa-circle-check"></i> Faculty Photo Enrolled for ${data.name || teacherId}! ${detectMsg}`;
                    }

                    this.showToast(`Enrolled faculty photo for ${data.name || teacherId}!`, "success");
                    this.fetchEnrolledTeachers();
                    this.fetchSessionStatus();
                } else {
                    this.showToast(data.detail || data.message || "Capture failed. Make sure face is visible to camera.", "error");
                }
            } catch (e) {
                console.error("Live teacher snap error:", e);
                this.showToast("Faculty face capture error: " + e.message, "error");
            } finally {
                if (snapBtn) {
                    snapBtn.disabled = false;
                    snapBtn.innerHTML = '<i class="fa-solid fa-camera"></i> SNAP & ENROLL TEACHER FACE';
                }
            }
        }
    },

    async fetchEnrolledStudents() {
        const tbody = document.getElementById('enrolledStudentsTableBody');
        const countBadge = document.getElementById('countStudentRoster');

        try {
            const res = await fetch(this.getApiUrl('/api/enroll/students'));
            const data = await res.json();
            const students = data.students || [];

            this.cachedStudentsList = students;
            this.renderLiveClassPresence();
            this.updateEmailRecipientCount();

            if (countBadge) countBadge.textContent = students.length;
            if (!tbody) return;

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

                const emailSnippet = s.email 
                    ? `<div style="font-size: 0.72rem; color: #64748b; margin-top: 2px;"><i class="fa-solid fa-envelope"></i> ${s.email}</div>` 
                    : '';

                tr.innerHTML = `
                    <td>${photoHtml}</td>
                    <td><strong>${s.student_id}</strong></td>
                    <td>
                        <div style="font-weight: 700; color: #1e293b;">${s.name}</div>
                        ${emailSnippet}
                    </td>
                    <td>${s.roll_number}</td>
                    <td><strong>${s.class_section}</strong></td>
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
            if (tbody) tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: #ef4444;">Failed to load roster.</td></tr>';
        }
    },

    async fetchEnrolledTeachers() {
        const tbody = document.getElementById('enrolledTeachersTableBody');
        const countBadge = document.getElementById('countTeacherRoster');

        try {
            const res = await fetch(this.getApiUrl('/api/enroll/teachers'));
            const data = await res.json();
            const teachers = data.teachers || [];

            this.cachedTeachersList = teachers;
            this.populateTeacherDropdownForRoutine();

            if (countBadge) countBadge.textContent = teachers.length;
            if (!tbody) return;

            tbody.innerHTML = '';
            if (teachers.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: #94a3b8; padding: 20px;">No registered faculty members found. Use the form above to register.</td></tr>';
                return;
            }

            teachers.forEach(t => {
                const tr = document.createElement('tr');
                const photoSrc = t.photo_path ? `${this.getApiUrl('/faces/' + t.photo_path.split('\\\\').pop().split('/').pop())}?t=${Date.now()}` : '';
                const photoHtml = photoSrc 
                    ? `<img src="${photoSrc}" style="width: 38px; height: 38px; border-radius: 6px; object-fit: cover; border: 1px solid rgba(16, 185, 129, 0.3);" onerror="this.outerHTML='<div style=\\'width:38px;height:38px;border-radius:6px;background:#ecfdf5;border:1px solid #a7f3d0;display:flex;align-items:center;justify-content:center;color:#059669;\\'><i class=\\'fa-solid fa-chalkboard-user\\'></i></div>'">`
                    : `<div style="width: 38px; height: 38px; border-radius: 6px; background: #ecfdf5; border: 1px solid #a7f3d0; display: flex; align-items: center; justify-content: center; color: #059669;"><i class="fa-solid fa-chalkboard-user"></i></div>`;

                const slotBadge = t.fingerprint_id !== null && t.fingerprint_id !== undefined
                    ? `<span style="display: inline-block; padding: 3px 8px; border-radius: 12px; background: rgba(79, 70, 229, 0.1); color: var(--accent-indigo); font-weight: 700; font-size: 0.72rem; border: 1px solid rgba(79, 70, 229, 0.2);">Slot #${t.fingerprint_id}</span>`
                    : `<span style="color: #94a3b8; font-size: 0.78rem;">None</span>`;

                tr.innerHTML = `
                    <td>${photoHtml}</td>
                    <td><strong>${t.teacher_id}</strong></td>
                    <td>${t.name}</td>
                    <td><span style="font-weight: 600; color: #334155;">${t.department || 'General'}</span></td>
                    <td>${slotBadge}</td>
                    <td><span style="display: inline-block; padding: 3px 8px; border-radius: 12px; background: rgba(16, 185, 129, 0.15); color: #10b981; font-weight: 700; font-size: 0.72rem; border: 1px solid rgba(16, 185, 129, 0.3);"><i class="fa-solid fa-check"></i> FACULTY ACTIVE</span></td>
                    <td>
                        <button class="btn-ctrl" onclick="App.deleteTeacher('${t.teacher_id}', '${(t.name || t.teacher_id).replace(/'/g, "\\'")}')" style="padding: 4px 10px; font-size: 0.72rem; background: rgba(239, 68, 68, 0.1); color: #ef4444; border-color: rgba(239, 68, 68, 0.3);">
                            <i class="fa-solid fa-trash-can"></i> Delete
                        </button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        } catch (e) {
            console.error("Error fetching enrolled teachers:", e);
            if (tbody) tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: #ef4444;">Failed to load faculty roster.</td></tr>';
        }
    },

    async deleteTeacher(teacherId, teacherName) {
        if (!confirm(`Are you sure you want to delete faculty member "${teacherName || teacherId}"?`)) {
            return;
        }

        try {
            const res = await fetch(this.getApiUrl(`/api/enroll/teacher/${encodeURIComponent(teacherId)}`), {
                method: 'DELETE'
            });
            const data = await res.json();
            if (res.ok && data.success) {
                this.showToast(`🗑️ Deleted faculty member: ${teacherName || teacherId}`, "info");
                this.fetchEnrolledTeachers();
                this.fetchSessionStatus();
            } else {
                this.showToast(data.detail || "Failed to delete faculty member", "error");
            }
        } catch (err) {
            console.error("Error deleting teacher:", err);
            this.showToast("Delete error: " + err.message, "error");
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

    initClassFilters() {
        const pills = document.querySelectorAll('.btn-class-pill');
        pills.forEach(pill => {
            pill.addEventListener('click', () => {
                pills.forEach(p => p.classList.remove('active'));
                pill.classList.add('active');
                this.selectedClassFilter = pill.getAttribute('data-class') || 'ALL';
                this.renderLiveClassPresence();
                this.checkTimetableStatus();
            });
        });
    },

    renderLiveClassPresence() {
        const grid = document.getElementById('liveStudentsPresenceGrid');
        const presentCountEl = document.getElementById('classPresentCount');
        const totalCountEl = document.getElementById('classTotalCount');
        if (!grid) return;

        const students = this.cachedStudentsList || [];
        const filter = this.selectedClassFilter || 'ALL';

        const filtered = filter === 'ALL'
            ? students
            : students.filter(s => (s.class_section || '').toUpperCase() === filter.toUpperCase());

        const presentCount = filtered.filter(s => this.presentStudents.has(s.student_id)).length;
        const totalCount = filtered.length;

        if (presentCountEl) presentCountEl.textContent = presentCount;
        if (totalCountEl) totalCountEl.textContent = totalCount;

        if (filtered.length === 0) {
            grid.innerHTML = `
                <div style="grid-column: 1 / -1; text-align: center; padding: 30px; color: #94a3b8; background: #f8fafc; border-radius: 10px; border: 1px dashed #cbd5e1;">
                    <i class="fa-solid fa-users-slash" style="font-size: 1.8rem; margin-bottom: 8px; color: #cbd5e1; display: block;"></i>
                    <strong style="color: #64748b;">No students enrolled for ${filter === 'ALL' ? 'any class' : filter}</strong>
                    <div style="font-size: 0.78rem; margin-top: 4px;">Enroll students in the Enrollment Studio to view live class presence.</div>
                </div>
            `;
            return;
        }

        grid.innerHTML = '';
        filtered.forEach(s => {
            const isPresent = this.presentStudents.has(s.student_id);
            const card = document.createElement('div');
            card.className = `student-presence-card ${isPresent ? 'is-present' : 'is-absent'}`;
            card.dataset.studentId = s.student_id;

            const photoSrc = s.photo_path 
                ? `${this.getApiUrl('/faces/' + s.photo_path.split('\\\\').pop().split('/').pop())}?t=${Date.now()}` 
                : '';
            const photoHtml = photoSrc
                ? `<img src="${photoSrc}" style="width: 42px; height: 42px; border-radius: 10px; object-fit: cover; border: 1px solid ${isPresent ? 'rgba(16, 185, 129, 0.4)' : 'rgba(239, 68, 68, 0.3)'};" onerror="this.outerHTML='<div class=\\'student-presence-avatar\\' style=\\'background: ${isPresent ? '#ecfdf5; color: #059669;' : '#fef2f2; color: #dc2626;'}\\'>${(s.name || 'S').charAt(0)}</div>'">`
                : `<div class="student-presence-avatar" style="background: ${isPresent ? '#ecfdf5; color: #059669;' : '#fef2f2; color: #dc2626;'}">${(s.name || 'S').charAt(0)}</div>`;

            const statusBadge = isPresent
                ? `<span class="badge-status-present"><i class="fa-solid fa-circle-check"></i> PRESENT</span>`
                : `<span class="badge-status-absent"><i class="fa-solid fa-circle-xmark"></i> ABSENT</span>`;

            const emailHtml = s.email 
                ? `<div style="font-size: 0.68rem; color: #64748b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 150px; margin-top: 2px;" title="${s.email}"><i class="fa-solid fa-envelope"></i> ${s.email}</div>`
                : '';

            card.innerHTML = `
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                    <div style="display: flex; align-items: center; gap: 10px; overflow: hidden;">
                        ${photoHtml}
                        <div style="overflow: hidden;">
                            <h4 style="margin: 0; font-size: 0.88rem; font-weight: 800; color: #0f172a; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 140px;" title="${s.name}">${s.name}</h4>
                            <p style="margin: 2px 0 0 0; font-size: 0.74rem; color: #64748b;">${s.roll_number} • <strong style="color: #475569;">${s.class_section}</strong></p>
                            ${emailHtml}
                        </div>
                    </div>
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 6px; padding-top: 6px; border-top: 1px solid ${isPresent ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)'};">
                    <span style="font-size: 0.68rem; font-weight: 700; color: #94a3b8;">${s.student_id}</span>
                    ${statusBadge}
                </div>
            `;
            grid.appendChild(card);
        });
    },

    initTimetableMonitor() {
        this.checkTimetableStatus();
        if (this.timetableMonitorInterval) clearInterval(this.timetableMonitorInterval);
        this.timetableMonitorInterval = setInterval(() => this.checkTimetableStatus(), 10000);
    },

    async checkTimetableStatus() {
        const targetClass = (this.selectedClassFilter && this.selectedClassFilter !== 'ALL')
            ? this.selectedClassFilter
            : 'CSE A';

        try {
            const res = await fetch(this.getApiUrl(`/api/timetable/status?class_name=${encodeURIComponent(targetClass)}`));
            if (!res.ok) return;
            const data = await res.json();
            const status = data.status || {};

            const card = document.getElementById('teacherPresenceCard');
            const teacherNameEl = document.getElementById('activeTeacherName');
            const timeSlotBadge = document.getElementById('activeTimeSlotBadge');
            const subjectNameEl = document.getElementById('activeSubjectName');
            const roomNameEl = document.getElementById('activeRoomName');
            const badgeContainer = document.getElementById('teacherPresenceBadgeContainer');

            if (!card) return;

            if (status.has_active_slot) {
                if (teacherNameEl) teacherNameEl.textContent = status.teacher_name || 'Scheduled Faculty';
                if (timeSlotBadge) timeSlotBadge.textContent = `${status.start_time} - ${status.end_time}`;
                if (subjectNameEl) subjectNameEl.textContent = `${status.subject} (${status.class_name})`;
                if (roomNameEl) roomNameEl.textContent = status.room_number || 'Room 101';

                if (status.teacher_present) {
                    card.classList.remove('alert-teacher-late');
                    card.style.background = '#f0fdf4';
                    card.style.borderColor = '#86efac';
                    if (badgeContainer) {
                        badgeContainer.innerHTML = `
                            <span class="badge-status-present" style="font-size: 0.82rem; padding: 6px 14px;">
                                <i class="fa-solid fa-chalkboard-user"></i> TEACHER PRESENT
                            </span>
                        `;
                    }
                } else {
                    if (status.is_late_alert) {
                        // >= 5 minutes late! Class blinks yellow showing teacher absent
                        card.classList.add('alert-teacher-late');
                        if (badgeContainer) {
                            badgeContainer.innerHTML = `
                                <span class="badge-status-warning" style="font-size: 0.82rem; padding: 6px 14px;">
                                    <i class="fa-solid fa-triangle-exclamation fa-beat"></i> TEACHER ABSENT (>5 MINS)
                                </span>
                            `;
                        }
                    } else {
                        // Absent but within 5-minute grace period
                        card.classList.remove('alert-teacher-late');
                        card.style.background = '#fef2f2';
                        card.style.borderColor = '#fca5a5';
                        const minsLeft = 5 - (status.elapsed_minutes || 0);
                        if (badgeContainer) {
                            badgeContainer.innerHTML = `
                                <span class="badge-status-absent" style="font-size: 0.82rem; padding: 6px 14px;">
                                    <i class="fa-solid fa-clock"></i> TEACHER PENDING (${minsLeft}m GRACE)
                                </span>
                            `;
                        }
                    }
                }
            } else {
                // No active slot currently scheduled
                card.classList.remove('alert-teacher-late');
                card.style.background = '#f8fafc';
                card.style.borderColor = 'var(--border-color)';
                if (teacherNameEl) teacherNameEl.textContent = `No Active Lecture (${targetClass})`;
                if (timeSlotBadge) timeSlotBadge.textContent = 'Standby Slot';
                if (subjectNameEl) subjectNameEl.textContent = 'No scheduled lecture period at this time';
                if (roomNameEl) roomNameEl.textContent = 'N/A';
                if (badgeContainer) {
                    badgeContainer.innerHTML = `
                        <span class="badge-status-absent" style="font-size: 0.82rem; padding: 6px 14px; opacity: 0.6; background: #e2e8f0; color: #475569; border-color: #cbd5e1;">
                            <i class="fa-solid fa-circle-info"></i> NO ACTIVE PERIOD
                        </span>
                    `;
                }
            }
        } catch (e) {
            console.warn("Could not check timetable status:", e);
        }
    },

    async fetchTimetableRoutines() {
        try {
            const res = await fetch(this.getApiUrl('/api/timetable/routines'));
            if (!res.ok) throw new Error("Failed to load routines");
            const data = await res.json();
            this.timetableRoutines = data.routines || [];
            this.renderTimetableRoutines();
        } catch (e) {
            console.error("Error fetching timetable routines:", e);
            const tbody = document.getElementById('routineTableBody');
            if (tbody) tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: #ef4444; padding: 16px;">Failed to load timetable routine.</td></tr>';
        }
    },

    renderTimetableRoutines() {
        const tbody = document.getElementById('routineTableBody');
        if (!tbody) return;

        const dayFilter = document.getElementById('filterRoutineDay') ? document.getElementById('filterRoutineDay').value : '';
        const classFilter = document.getElementById('filterRoutineClass') ? document.getElementById('filterRoutineClass').value : '';

        let filtered = this.timetableRoutines || [];
        if (dayFilter) {
            filtered = filtered.filter(r => (r.day_of_week || '').toLowerCase() === dayFilter.toLowerCase());
        }
        if (classFilter) {
            filtered = filtered.filter(r => (r.class_name || '').toUpperCase() === classFilter.toUpperCase());
        }

        if (filtered.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: #94a3b8; padding: 24px;">No routine periods found. Add a period or upload CSV above.</td></tr>';
            return;
        }

        tbody.innerHTML = '';
        filtered.forEach(r => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${r.day_of_week}</strong></td>
                <td><span class="badge" style="font-size: 0.72rem; background: #f1f5f9; color: #334155; border: 1px solid #cbd5e1;">${r.start_time} - ${r.end_time}</span></td>
                <td><span style="font-weight: 700; color: var(--accent-indigo);">${r.class_name}</span></td>
                <td><strong>${r.subject}</strong></td>
                <td>${r.teacher_name || r.teacher_id || 'Unassigned'}</td>
                <td>${r.room_number || 'Room 101'}</td>
                <td>
                    <button class="btn-ctrl" onclick="App.deleteRoutine(${r.id})" style="padding: 4px 10px; font-size: 0.72rem; color: #ef4444; border-color: rgba(239, 68, 68, 0.3); background: rgba(239, 68, 68, 0.08);">
                        <i class="fa-solid fa-trash-can"></i>
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    },

    async handleRoutineSubmit(e) {
        e.preventDefault();
        const className = document.getElementById('routineClass').value;
        const day = document.getElementById('routineDay').value;
        const start = document.getElementById('routineStart').value;
        const end = document.getElementById('routineEnd').value;
        const subject = document.getElementById('routineSubject').value.trim();
        const teacherSelect = document.getElementById('routineTeacherSelect');
        const teacherId = teacherSelect.value;
        const teacherName = teacherSelect.options[teacherSelect.selectedIndex]?.dataset.name || teacherId;
        const room = document.getElementById('routineRoom').value.trim() || 'Room 101';

        if (!className || !day || !start || !end || !subject || !teacherId) {
            this.showToast("Please fill in all required routine fields", "error");
            return;
        }

        try {
            const res = await fetch(this.getApiUrl('/api/timetable/routine'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    class_name: className,
                    day_of_week: day,
                    start_time: start,
                    end_time: end,
                    subject: subject,
                    teacher_id: teacherId,
                    teacher_name: teacherName,
                    room_number: room
                })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "Failed to add routine period");

            this.showToast(`Added ${subject} for ${className} (${day})`, "success");
            document.getElementById('timetableForm').reset();
            document.getElementById('routineClass').value = className;
            document.getElementById('routineDay').value = day;
            this.fetchTimetableRoutines();
            this.checkTimetableStatus();
        } catch (err) {
            this.showToast("Routine error: " + err.message, "error");
        }
    },

    async handleRoutineUpload(file) {
        if (!file) return;
        const formData = new FormData();
        formData.append('file', file);

        this.showToast(`Uploading ${file.name}...`, "info");

        try {
            const res = await fetch(this.getApiUrl('/api/timetable/upload'), {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "Failed to upload timetable routine");

            const count = data.imported_count !== undefined ? data.imported_count : (data.count !== undefined ? data.count : 0);
            this.showToast(`Imported ${count} periods from ${file.name}!`, "success");
            this.fetchTimetableRoutines();
            this.checkTimetableStatus();
        } catch (e) {
            this.showToast("Upload failed: " + e.message, "error");
        }
    },

    async deleteRoutine(routineId) {
        if (!confirm("Are you sure you want to delete this scheduled routine period?")) return;

        try {
            const res = await fetch(this.getApiUrl(`/api/timetable/routine/${routineId}`), {
                method: 'DELETE'
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "Failed to delete routine");

            this.showToast("Deleted routine period", "info");
            this.fetchTimetableRoutines();
            this.checkTimetableStatus();
        } catch (e) {
            this.showToast("Delete error: " + e.message, "error");
        }
    },

    async clearAllTimetableRoutines() {
        if (!confirm("Are you sure you want to clear the ENTIRE timetable routine schedule?")) return;

        try {
            const res = await fetch(this.getApiUrl('/api/timetable/routines/all'), {
                method: 'DELETE'
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "Failed to clear routines");

            this.showToast("All timetable routines cleared", "info");
            this.fetchTimetableRoutines();
            this.checkTimetableStatus();
        } catch (e) {
            this.showToast("Clear error: " + e.message, "error");
        }
    },

    downloadSampleCsv() {
        const sampleCsv = `class_name,day_of_week,start_time,end_time,subject,teacher_name,teacher_id,room_number
CSE A,Monday,09:00,10:00,Operating Systems,Prof. Alan Turing,FAC-CSE-01,Room 101
CSE A,Monday,10:00,11:00,Database Systems,Prof. Ada Lovelace,FAC-CSE-02,Room 102
CSE B,Monday,09:00,10:00,Data Structures,Prof. Alan Turing,FAC-CSE-01,Room 103
CSE AIML,Monday,11:00,12:00,Machine Learning,Prof. Geoffrey Hinton,FAC-AIML-01,Lab 1
CE,Monday,09:00,10:00,Structural Analysis,Prof. John Smeaton,FAC-CE-01,Hall A
ME,Monday,10:00,11:00,Thermodynamics,Prof. James Watt,FAC-ME-01,Room 201
ECE,Monday,09:00,10:00,Signals & Systems,Prof. Claude Shannon,FAC-ECE-01,Room 301
CSE A,Tuesday,09:00,10:00,Computer Networks,Prof. Alan Turing,FAC-CSE-01,Room 101`;

        const blob = new Blob([sampleCsv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'timetable_routine_sample.csv';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        this.showToast("Downloaded sample timetable CSV template", "success");
    },

    populateTeacherDropdownForRoutine() {
        const sel = document.getElementById('routineTeacherSelect');
        if (!sel) return;

        const teachers = this.cachedTeachersList || [];
        sel.innerHTML = '<option value="" disabled selected>Select Teacher</option>';

        if (teachers.length === 0) {
            sel.innerHTML += '<option value="FAC-01" data-name="Faculty Member">Faculty Member (FAC-01)</option>';
            return;
        }

        teachers.forEach(t => {
            const opt = document.createElement('option');
            opt.value = t.teacher_id;
            opt.dataset.name = t.name;
            opt.textContent = `${t.name} (${t.teacher_id} - ${t.department || 'Dept'})`;
            sel.appendChild(opt);
        });
    },

    initEmailJS() {
        const saved = localStorage.getItem('attendance_emailjs_config');
        if (saved) {
            try {
                this.emailjsConfig = JSON.parse(saved);
                const sEl = document.getElementById('emailjsServiceId');
                const tEl = document.getElementById('emailjsTemplateId');
                const pEl = document.getElementById('emailjsPublicKey');
                if (sEl && this.emailjsConfig.serviceId) sEl.value = this.emailjsConfig.serviceId;
                if (tEl && this.emailjsConfig.templateId) tEl.value = this.emailjsConfig.templateId;
                if (pEl && this.emailjsConfig.publicKey) pEl.value = this.emailjsConfig.publicKey;

                if (window.emailjs && this.emailjsConfig.publicKey) {
                    window.emailjs.init(this.emailjsConfig.publicKey);
                    console.log("EmailJS initialized with public key.");
                }
            } catch (e) {
                console.warn("Could not parse saved EmailJS config:", e);
            }
        }
    },

    saveEmailjsConfig() {
        const sEl = document.getElementById('emailjsServiceId');
        const tEl = document.getElementById('emailjsTemplateId');
        const pEl = document.getElementById('emailjsPublicKey');

        const serviceId = sEl ? sEl.value.trim() : '';
        const templateId = tEl ? tEl.value.trim() : '';
        const publicKey = pEl ? pEl.value.trim() : '';

        this.emailjsConfig = { serviceId, templateId, publicKey };
        localStorage.setItem('attendance_emailjs_config', JSON.stringify(this.emailjsConfig));

        if (window.emailjs && publicKey) {
            window.emailjs.init(publicKey);
        }

        this.showToast("EmailJS configuration saved successfully!", "success");
    },

    updateEmailRecipientCount() {
        const countEl = document.getElementById('emailRecipientCount');
        if (!countEl) return;
        const students = this.cachedStudentsList || [];
        const withEmail = students.filter(s => s.email && s.email.includes('@'));
        countEl.textContent = `${withEmail.length} Students (of ${students.length} Total)`;
    },

    previewDailyEmailSummary() {
        const box = document.getElementById('emailDispatchProgressBox');
        if (!box) return;

        const students = this.cachedStudentsList || [];
        const sampleStudent = students.find(s => s.email && s.email.includes('@')) || {
            name: "John Doe",
            student_id: "STU-2026-001",
            roll_number: "CS-101",
            class_section: "CSE A",
            email: "student@campus.edu"
        };

        const isPresent = this.presentStudents.has(sampleStudent.student_id);
        const todayDate = new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });

        box.style.display = 'block';
        box.innerHTML = `
            <strong>Preview Email for: ${sampleStudent.name} &lt;${sampleStudent.email}&gt;</strong><br>
            --------------------------------------------------------<br>
            Subject: Daily Attendance Summary - ${todayDate}<br>
            Dear ${sampleStudent.name},<br>
            Your lecture attendance status for ${todayDate} (${sampleStudent.class_section}) is:<br>
            Status: ${isPresent ? '🟢 PRESENT' : '🔴 ABSENT'}<br>
            Roll Number: ${sampleStudent.roll_number} | ID: ${sampleStudent.student_id}<br>
            Daily Verification: Face Recognition Edge Pipeline Verified.<br>
            --------------------------------------------------------
        `;
        this.showToast("Preview generated below", "info");
    },

    async dispatchDailyAttendanceEmails() {
        const { serviceId, templateId, publicKey } = this.emailjsConfig;
        if (!serviceId || !templateId || !publicKey) {
            this.showToast("Please fill and save Service ID, Template ID, and Public Key first", "error");
            return;
        }

        const students = this.cachedStudentsList || [];
        const targets = students.filter(s => s.email && s.email.includes('@'));

        if (targets.length === 0) {
            this.showToast("No students have registered email addresses to send summaries to", "error");
            return;
        }

        const box = document.getElementById('emailDispatchProgressBox');
        const btn = document.getElementById('btnDispatchDailyEmails');
        if (box) {
            box.style.display = 'block';
            box.innerHTML = `Starting dispatch to ${targets.length} student(s)...<br>`;
        }
        if (btn) btn.disabled = true;

        if (window.emailjs) {
            window.emailjs.init(publicKey);
        }

        const todayDate = new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric', year: 'numeric' });
        let sentCount = 0;
        let failCount = 0;

        for (const s of targets) {
            const isPresent = this.presentStudents.has(s.student_id);
            const templateParams = {
                to_email: s.email,
                to_name: s.name,
                student_id: s.student_id,
                roll_number: s.roll_number,
                class_section: s.class_section,
                date: todayDate,
                attendance_status: isPresent ? 'PRESENT' : 'ABSENT',
                summary_details: `Daily attendance for ${todayDate}: Student was marked ${isPresent ? 'PRESENT (Verified)' : 'ABSENT'}.`,
                college_name: "Institute of Engineering & Technology"
            };

            try {
                if (window.emailjs) {
                    await window.emailjs.send(serviceId, templateId, templateParams);
                } else {
                    throw new Error("EmailJS SDK not loaded");
                }
                sentCount++;
                if (box) box.innerHTML += `✅ Sent summary to ${s.name} (${s.email})<br>`;
            } catch (err) {
                failCount++;
                if (box) box.innerHTML += `❌ Failed for ${s.name} (${s.email}): ${err.text || err.message}<br>`;
            }
        }

        if (btn) btn.disabled = false;
        this.showToast(`Daily emails sent: ${sentCount} succeeded, ${failCount} failed`, sentCount > 0 ? "success" : "error");
    },

    async fetchTodayAttendance() {
        try {
            const res = await fetch(this.getApiUrl('/api/attendance/records?limit=100'));
            if (res.ok) {
                const data = await res.json();
                if (data.records && Array.isArray(data.records)) {
                    const todayStr = new Date().toISOString().split('T')[0];
                    data.records.forEach(r => {
                        if (r.entry_time && r.entry_time.startsWith(todayStr)) {
                            this.presentStudents.add(r.student_id);
                        }
                    });
                    this.renderLiveClassPresence();
                }
            }
        } catch (e) {
            console.warn("Could not pre-fetch today's attendance records:", e);
        }
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
