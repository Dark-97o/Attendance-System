"""
Edge-optimized Face Detection and Recognition Engine for Raspberry Pi 5.
Combines OpenCV multi-scale detection, CLAHE lighting compensation,
feature vector embedding generation, and cosine distance nearest-neighbor lookup.
"""

import os
import cv2
import json
import logging
import threading
import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from database.models import DatabaseManager
from engine.preprocessor import LightingPreprocessor
from engine.tracker import MultiFaceTracker, TrackedFace

logger = logging.getLogger("attendance.face_engine")

class FaceEngine:
    """Core Face Recognition Engine optimized for ARM Cortex-A76 (Raspberry Pi 5)."""

    def __init__(self, db: DatabaseManager, similarity_threshold: float = 0.65, frame_skip: int = 1):
        self.db = db
        self.similarity_threshold = similarity_threshold
        self.frame_skip = frame_skip
        self.frame_counter = 0

        self.preprocessor = LightingPreprocessor()
        self.tracker = MultiFaceTracker(max_disappeared=15, iou_threshold=0.3)

        # Initialize Haar Cascade Fallback
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cascade_candidates = [
            os.path.join(base_dir, "models", "haarcascade_frontalface_default.xml"),
            os.path.join(getattr(cv2.data, "haarcascades", ""), "haarcascade_frontalface_default.xml")
        ]
        self.face_cascade = None
        for candidate in cascade_candidates:
            if candidate and os.path.exists(candidate):
                try:
                    self.face_cascade = cv2.CascadeClassifier(candidate)
                    logger.info(f"Loaded Haar cascade fallback from {candidate}")
                    break
                except Exception as e:
                    logger.warning(f"Could not load Haar cascade from {candidate}: {e}")
        if self.face_cascade is None:
            logger.warning("Haar cascade file not available; relying on YuNet neural face detector.")
        self.detector_lock = threading.Lock()

        # Initialize YuNet Deep Neural Network Face Detector (High accuracy under backlight/angles)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        yunet_path = os.path.join(base_dir, "models", "yunet.onnx")
        self.yunet = None
        if os.path.exists(yunet_path) and hasattr(cv2, 'FaceDetectorYN'):
            try:
                self.yunet = cv2.FaceDetectorYN.create(yunet_path, "", (640, 480), score_threshold=0.50, nms_threshold=0.35)
                logger.info("Initialized YuNet Deep Neural Network Face Detector (25+ FPS)")
            except Exception as ye:
                logger.warning(f"Could not load YuNet detector: {ye}")

        # In-memory enrolled face vectors cache: {student_id: [vector_1, vector_2, ...]}
        self.enrolled_cache: Dict[str, List[np.ndarray]] = {}
        self.student_metadata: Dict[str, Dict[str, Any]] = {}
        self.refresh_enrolled_cache()

        # Cached detections between frames for smooth display
        self.last_tracked_faces: List[TrackedFace] = []

    def detect_faces(self, image_bgr: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Thread-safe face detection using YuNet Deep Neural Network (with Haar Cascade fallback).
        Returns a list of (x, y, w, h) bounding boxes.
        """
        with self.detector_lock:
            img = np.ascontiguousarray(image_bgr)
            h, w = img.shape[:2]

            # 1. Primary: YuNet Deep Learning Detector
            if self.yunet is not None:
                try:
                    self.yunet.setInputSize((w, h))
                    _, faces = self.yunet.detect(img)
                    if faces is not None and len(faces) > 0:
                        boxes = []
                        for f in faces:
                            bx, by, bw, bh = int(f[0]), int(f[1]), int(f[2]), int(f[3])
                            bx = max(0, bx)
                            by = max(0, by)
                            bw = min(bw, w - bx)
                            bh = min(bh, h - by)
                            if bw >= 24 and bh >= 24:
                                boxes.append((bx, by, bw, bh))
                        if len(boxes) > 1:
                            kept = []
                            for b in boxes:
                                overlap = False
                                for k in kept:
                                    ix = max(b[0], k[0])
                                    iy = max(b[1], k[1])
                                    iw = max(0, min(b[0] + b[2], k[0] + k[2]) - ix)
                                    ih = max(0, min(b[1] + b[3], k[1] + k[3]) - iy)
                                    inter = iw * ih
                                    if inter / float(b[2] * b[3] + 1e-6) > 0.35:
                                        overlap = True
                                        break
                                if not overlap:
                                    kept.append(b)
                            boxes = kept
                        if len(boxes) > 0:
                            return boxes
                except Exception as ye:
                    logger.warning(f"YuNet detection warning: {ye}")

            # 2. Fallback: Haar Cascade
            if self.face_cascade is not None:
                try:
                    gray = np.ascontiguousarray(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
                    haar_faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(30, 30))
                    return [(int(x), int(y), int(bw), int(bh)) for (x, y, bw, bh) in haar_faces]
                except Exception as he:
                    logger.warning(f"Haar detection warning: {he}")
            return []

    def refresh_enrolled_cache(self):
        """Loads all student face embeddings from SQLite into memory for sub-millisecond vector search."""
        records = self.db.get_all_enrolled_faces()
        self.enrolled_cache.clear()
        self.student_metadata.clear()

        for rec in records:
            sid = rec["student_id"]
            vec = np.array(rec["embedding"], dtype=np.float32)
            # Normalize vector to unit length
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm

            if sid not in self.enrolled_cache:
                self.enrolled_cache[sid] = []
                self.student_metadata[sid] = {
                    "name": rec["name"],
                    "roll_number": rec["roll_number"],
                    "class_section": rec["class_section"],
                    "photo_path": rec["photo_path"]
                }
            self.enrolled_cache[sid].append(vec)

        logger.info(f"Loaded {len(self.enrolled_cache)} enrolled students with {sum(len(v) for v in self.enrolled_cache.values())} biometric templates")

    def extract_face_embedding(self, face_bgr: np.ndarray) -> np.ndarray:
        """
        Computes a compact, robust 128-dimensional multi-region spatial gradient embedding.
        Invariance properties: robust to illumination gradients, minor pose, and scale.
        """
        # Resize to standard canonical size 112x112
        face_norm = cv2.resize(face_bgr, (112, 112))
        gray = cv2.cvtColor(face_norm, cv2.COLOR_BGR2GRAY)
        
        # Apply local contrast normalization
        gray = cv2.equalizeHist(gray)

        # Divide into 4x4 spatial blocks (16 cells)
        cells_x, cells_y = 4, 4
        h, w = gray.shape
        cell_h, cell_w = h // cells_y, w // cells_x

        # Compute Sobel gradients in X and Y
        sobel_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        magnitude, angle = cv2.cartToPolar(sobel_x, sobel_y, angleInDegrees=True)

        features = []
        for i in range(cells_y):
            for j in range(cells_x):
                cell_mag = magnitude[i * cell_h:(i + 1) * cell_h, j * cell_w:(j + 1) * cell_w]
                cell_ang = angle[i * cell_h:(i + 1) * cell_h, j * cell_w:(j + 1) * cell_w]
                
                # 8-bin orientation histogram per cell -> 16 * 8 = 128 dimensions
                hist, _ = np.histogram(cell_ang, bins=8, range=(0, 360), weights=cell_mag)
                features.extend(hist)

        vec = np.array(features, dtype=np.float32)
        norm = np.linalg.norm(vec)
        if norm > 1e-6:
            vec = vec / norm
        return vec

    def identify_face(self, face_embedding: np.ndarray) -> Tuple[Optional[str], float, Optional[Dict[str, Any]]]:
        """
        Searches the in-memory enrolled vector database using Cosine Similarity.
        Returns (student_id, confidence, metadata_dict)
        """
        if not self.enrolled_cache:
            return None, 0.0, None

        best_sid = None
        best_score = -1.0

        for sid, templates in self.enrolled_cache.items():
            for tmpl in templates:
                # Cosine similarity between unit normalized vectors is their dot product
                sim = float(np.dot(face_embedding, tmpl))
                if sim > best_score:
                    best_score = sim
                    best_sid = sid

        if best_score >= self.similarity_threshold and best_sid:
            return best_sid, round(best_score, 3), self.student_metadata.get(best_sid)
        
        return None, round(best_score, 3), None

    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, List[Dict[str, Any]], dict]:
        """
        Processes a video frame through the complete pipeline:
        1. Lighting Compensation (CLAHE)
        2. Multi-scale Face Detection (with frame-skipping optimization for Pi 5)
        3. Feature Extraction & Nearest-Neighbor Identification
        4. Spatial IoU Tracking across frames
        5. Visual HUD Annotation
        Returns: (annotated_frame, list_of_recognized_students, lighting_metrics)
        """
        self.frame_counter += 1
        h, w, _ = frame.shape

        # Step 1: Lighting enhancement
        enhanced_frame, light_metrics = self.preprocessor.enhance(frame)

        # Frame skipping: on skipped frames, use tracker prediction to reduce compute
        should_run_detection = (self.frame_counter % self.frame_skip == 0)

        detected_faces = []
        recognized_students = []

        if should_run_detection:
            boxes = self.detect_faces(enhanced_frame)
            for (x, y, bw, bh) in boxes:
                # Crop face
                face_crop = enhanced_frame[y:y + bh, x:x + bw]
                if face_crop.size == 0:
                    continue

                # Extract 128D embedding
                emb = self.extract_face_embedding(face_crop)
                sid, conf, meta = self.identify_face(emb)

                detected_faces.append({
                    "bbox": (x, y, bw, bh),
                    "identity": sid,
                    "confidence": conf,
                    "metadata": meta
                })

            # Update tracker
            self.last_tracked_faces = self.tracker.update(detected_faces)
        else:
            # Use tracker to maintain persistence
            self.last_tracked_faces = self.tracker.update([])

        # Draw HUD overlays on output frame
        annotated_frame = enhanced_frame.copy()

        for tf in self.last_tracked_faces:
            x, y, bw, bh = tf.bbox
            sid = tf.identity
            conf = tf.confidence
            meta = self.student_metadata.get(sid) if sid else None

            if sid and meta and conf >= self.similarity_threshold:
                active_session = self.db.get_active_session()
                if active_session:
                    # Lecture Active: Student Verified & Marked
                    box_color = (46, 204, 113)  # Emerald Green
                    label = f"✓ {meta['name']} (PRESENT)"
                    sub_label = f"Match: {int(conf * 100)}% | Roll: {meta['roll_number']}"
                else:
                    # Lecture Inactive: Face Recognized, Session Pending
                    box_color = (0, 215, 255)  # Cyan/Gold
                    label = f"• {meta['name']} (Enrolled)"
                    sub_label = f"Session Inactive | Match: {int(conf * 100)}%"
                
                recognized_students.append({
                    "student_id": sid,
                    "name": meta["name"],
                    "roll_number": meta["roll_number"],
                    "class_section": meta["class_section"],
                    "confidence": conf,
                    "track_id": tf.track_id,
                    "frames_active": tf.frames_active
                })
            else:
                # Unknown / Unenrolled face (Amber Warning box)
                box_color = (0, 165, 255)
                label = "Unregistered Face"
                sub_label = "Go to Enrollment Studio to Register"

            # Draw sleek HUD corners & bounding box
            self._draw_hud_box(annotated_frame, (x, y, bw, bh), box_color, label, sub_label)

        return annotated_frame, recognized_students, light_metrics

    def _draw_hud_box(self, img: np.ndarray, bbox: Tuple[int, int, int, int], color: tuple, label: str, sub_label: str):
        """Draws modern corner-bracket HUD elements around faces."""
        x, y, w, h = bbox
        corner_len = min(20, w // 4, h // 4)
        thickness = 2

        # Primary box with rounded feel / corners
        cv2.rectangle(img, (x, y), (x + w, y + h), color, 1)

        # High-tech corner brackets
        # Top-left
        cv2.line(img, (x, y), (x + corner_len, y), color, thickness)
        cv2.line(img, (x, y), (x, y + corner_len), color, thickness)
        # Top-right
        cv2.line(img, (x + w, y), (x + w - corner_len, y), color, thickness)
        cv2.line(img, (x + w, y), (x + w, y + corner_len), color, thickness)
        # Bottom-left
        cv2.line(img, (x, y + h), (x + corner_len, y + h), color, thickness)
        cv2.line(img, (x, y + h), (x, y + h - corner_len), color, thickness)
        # Bottom-right
        cv2.line(img, (x + w, y + h), (x + w - corner_len, y + h), color, thickness)
        cv2.line(img, (x + w, y + h), (x + w, y + h - corner_len), color, thickness)

        # Label Banner
        banner_y = max(y - 28, 10)
        cv2.rectangle(img, (x, banner_y), (x + max(200, w), banner_y + 24), (20, 20, 25), -1)
        cv2.rectangle(img, (x, banner_y), (x + max(200, w), banner_y + 24), color, 1)
        cv2.putText(img, label, (x + 6, banner_y + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

    def enroll_face_image(self, student_id: str, image_bgr: np.ndarray) -> Tuple[bool, str]:
        """Detects face in provided image and stores embedding into database."""
        image_bgr = np.ascontiguousarray(image_bgr)
        boxes = self.detect_faces(image_bgr)

        if len(boxes) == 0:
            # If detector misses under extreme angles, use center crop fallback
            h, w = image_bgr.shape[:2]
            crop = image_bgr[h//6:5*h//6, w//6:5*w//6]
        else:
            # Take largest detected face
            fx, fy, fw, fh = max(boxes, key=lambda b: b[2] * b[3])
            crop = image_bgr[fy:fy + fh, fx:fx + fw]

        emb = self.extract_face_embedding(crop).tolist()
        self.db.add_face_embedding(student_id, emb)
        self.refresh_enrolled_cache()
        return True, f"Face embedding enrolled for {student_id}"
