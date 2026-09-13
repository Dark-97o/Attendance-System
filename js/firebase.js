/**
 * Firebase Client Integration Module (100% Free Spark Tier)
 * Handles Firebase Authentication and Cloud Firestore Database Sync.
 * Does NOT require paid Firebase Cloud Storage; photos are saved locally on Edge device
 * and lightweight thumbnail vectors/base64 previews are synced to Firestore.
 */

import { initializeApp } from "https://www.gstatic.com/firebasejs/11.4.0/firebase-app.js";
import { 
    getAuth, 
    signInWithEmailAndPassword, 
    createUserWithEmailAndPassword, 
    signOut, 
    onAuthStateChanged,
    updateProfile,
    sendPasswordResetEmail,
    setPersistence,
    browserLocalPersistence
} from "https://www.gstatic.com/firebasejs/11.4.0/firebase-auth.js";
import { 
    getFirestore, 
    collection, 
    doc, 
    setDoc, 
    addDoc, 
    serverTimestamp 
} from "https://www.gstatic.com/firebasejs/11.4.0/firebase-firestore.js";

// Production Firebase Configuration (attend-78e68)
const firebaseConfig = {
    apiKey: "AIzaSyAJ-sh81SUhnzapkRRqIlou2lN2n9JGeYU",
    authDomain: "attend-78e68.firebaseapp.com",
    projectId: "attend-78e68",
    messagingSenderId: "79454587621",
    appId: "1:79454587621:web:da3db646b7d289c814220c"
};

// Initialize Firebase Core Services (Auth + Firestore only - 100% Free Tier)
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);

// Explicitly lock persistence to local browser storage to prevent cross-origin iframe flicker
try {
    setPersistence(auth, browserLocalPersistence).catch((err) => {
        console.warn("[Firebase Auth] setPersistence note:", err);
    });
} catch (e) {}

// Global Firebase Bridge for Dashboard Integration
const FirebaseBridge = {
    app,
    auth,
    db,
    currentUser: null,

    // --- AUTHENTICATION METHODS ---

    async signIn(email, password) {
        try {
            const userCredential = await signInWithEmailAndPassword(auth, email, password);
            this.currentUser = userCredential.user;
            try {
                localStorage.setItem('attendance_auth_user', JSON.stringify({
                    email: userCredential.user.email,
                    displayName: userCredential.user.displayName || userCredential.user.email,
                    uid: userCredential.user.uid
                }));
            } catch (e) {}
            return { success: true, user: userCredential.user };
        } catch (error) {
            console.error("Firebase Auth SignIn Error:", error);
            return { success: false, error: error.message, code: error.code };
        }
    },

    async registerUser(email, password, displayName = "") {
        try {
            const userCredential = await createUserWithEmailAndPassword(auth, email, password);
            if (displayName && userCredential.user) {
                await updateProfile(userCredential.user, { displayName });
            }
            this.currentUser = userCredential.user;
            try {
                localStorage.setItem('attendance_auth_user', JSON.stringify({
                    email: userCredential.user.email,
                    displayName: userCredential.user.displayName || userCredential.user.email,
                    uid: userCredential.user.uid
                }));
            } catch (e) {}
            return { success: true, user: userCredential.user };
        } catch (error) {
            console.error("Firebase Auth Register Error:", error);
            return { success: false, error: error.message, code: error.code };
        }
    },

    async signOutUser() {
        try {
            try {
                localStorage.removeItem('attendance_auth_user');
            } catch (e) {}
            await signOut(auth);
            this.currentUser = null;
            return { success: true };
        } catch (error) {
            console.error("Firebase Auth SignOut Error:", error);
            return { success: false, error: error.message };
        }
    },

    async resetPassword(email) {
        try {
            await sendPasswordResetEmail(auth, email);
            console.log(`[Firebase Auth] Password reset email sent to: ${email}`);
            return { success: true };
        } catch (error) {
            console.error("Firebase Password Reset Error:", error);
            return { success: false, error: error.message, code: error.code };
        }
    },

    onAuthChange(callback) {
        return onAuthStateChanged(auth, (user) => {
            this.currentUser = user;
            if (user) {
                try {
                    localStorage.setItem('attendance_auth_user', JSON.stringify({
                        email: user.email,
                        displayName: user.displayName || user.email,
                        uid: user.uid
                    }));
                } catch (e) {}
            }
            callback(user);
        });
    },

    // --- CLOUD FIRESTORE METHODS (REAL-TIME SYNC - 100% FREE) ---

    async syncStudentProfile(studentData) {
        try {
            const studentRef = doc(db, "students", String(studentData.student_id));
            await setDoc(studentRef, {
                student_id: studentData.student_id,
                name: studentData.name,
                roll_number: studentData.roll_number || "",
                class_section: studentData.class_section || "",
                photo_thumbnail: studentData.photo_preview || studentData.photo_thumbnail || "",
                updated_at: serverTimestamp()
            }, { merge: true });
            console.log(`[Firestore] Synced student profile ${studentData.student_id} to Cloud Firestore.`);
            return { success: true };
        } catch (error) {
            console.warn("[Firestore] Student sync warning:", error);
            return { success: false, error: error.message };
        }
    },

    async syncAttendanceRecord(recordData) {
        try {
            const attColl = collection(db, "attendance_records");
            await addDoc(attColl, {
                student_id: recordData.student_id,
                student_name: recordData.student_name || recordData.name || "",
                session_id: recordData.session_id || null,
                session_code: recordData.session_code || "",
                timestamp: recordData.timestamp || new Date().toISOString(),
                confidence: recordData.confidence || 0.9,
                status: "PRESENT",
                created_at: serverTimestamp()
            });
            return { success: true };
        } catch (error) {
            console.warn("[Firestore] Attendance sync warning:", error);
            return { success: false, error: error.message };
        }
    },

    async syncSession(sessionData) {
        try {
            const sessionRef = doc(db, "lecture_sessions", String(sessionData.id || sessionData.session_code));
            await setDoc(sessionRef, {
                session_code: sessionData.session_code,
                teacher_id: sessionData.teacher_id,
                teacher_name: sessionData.teacher_name || "Faculty Member",
                course_code: sessionData.course_code,
                course_name: sessionData.course_name,
                room_number: sessionData.room_number || "Room 101",
                start_time: sessionData.start_time,
                end_time: sessionData.end_time || null,
                is_active: sessionData.is_active ? 1 : 0,
                updated_at: serverTimestamp()
            }, { merge: true });
            return { success: true };
        } catch (error) {
            console.warn("[Firestore] Session sync warning:", error);
            return { success: false, error: error.message };
        }
    }
};

// Expose globally for dashboard scripts
window.FirebaseBridge = FirebaseBridge;

// Dispatch event once initialized
window.dispatchEvent(new CustomEvent("firebase-bridge-ready", { detail: FirebaseBridge }));
export default FirebaseBridge;
