"""
Centroid and IoU Multi-Face Tracker.
Maintains persistent track IDs across frames to prevent jitter and support hysteresis logging.
"""

import numpy as np
from typing import List, Dict, Tuple, Any, Optional
from collections import OrderedDict

def calculate_iou(boxA: Tuple[int, int, int, int], boxB: Tuple[int, int, int, int]) -> float:
    """Calculates Intersection over Union between two bounding boxes (x, y, w, h)."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[0] + boxA[2], boxB[0] + boxB[2])
    yB = min(boxA[1] + boxA[3], boxB[1] + boxB[3])

    interArea = max(0, xB - xA) * max(0, yB - yA)
    boxAArea = boxA[2] * boxA[3]
    boxBArea = boxB[2] * boxB[3]

    iou = interArea / float(boxAArea + boxBArea - interArea + 1e-6)
    return float(iou)

class TrackedFace:
    def __init__(self, track_id: int, bbox: Tuple[int, int, int, int], identity: Optional[str] = None, confidence: float = 0.0, landmarks: Optional[np.ndarray] = None):
        self.track_id = track_id
        self.bbox = bbox
        self.identity = identity
        self.confidence = confidence
        self.disappeared = 0
        self.frames_active = 1
        self.first_seen_time = None
        self.last_seen_time = None
        self.identity_votes: Dict[str, int] = {}
        if identity:
            self.identity_votes[identity] = 1

        # Liveness & anti-spoofing diagnostics
        self.landmarks = landmarks
        self.landmark_history: List[np.ndarray] = []
        if landmarks is not None:
            self.landmark_history.append(landmarks)
        self.is_live: bool = True
        self.liveness_score: float = 1.0
        self.liveness_reason: str = "Evaluating..."
        self.consecutive_spoof_frames: int = 0
        self.consecutive_live_frames: int = 0

    def update(self, bbox: Tuple[int, int, int, int], identity: Optional[str] = None, confidence: float = 0.0, landmarks: Optional[np.ndarray] = None, liveness_info: Optional[Dict[str, Any]] = None):
        self.bbox = bbox
        self.disappeared = 0
        self.frames_active += 1
        if identity:
            self.identity_votes[identity] = self.identity_votes.get(identity, 0) + 1
            # Majority vote for identity
            self.identity = max(self.identity_votes, key=self.identity_votes.get)
            self.confidence = max(self.confidence, confidence)

        if landmarks is not None:
            self.landmarks = landmarks
            self.landmark_history.append(landmarks)
            if len(self.landmark_history) > 25:
                self.landmark_history.pop(0)

        if liveness_info:
            is_live_now = liveness_info.get("is_live", True)
            self.liveness_score = liveness_info.get("texture_score", 1.0)
            if not is_live_now:
                self.consecutive_spoof_frames += 1
                self.consecutive_live_frames = 0
                self.is_live = False
                self.liveness_reason = liveness_info.get("reason", "Spoof Attack")
            else:
                self.consecutive_live_frames += 1
                self.consecutive_spoof_frames = 0
                self.is_live = True
                self.liveness_reason = "Verified Live Human"


class MultiFaceTracker:
    """Tracks multiple faces across frames using Centroid Distance and IoU."""

    def __init__(self, max_disappeared: int = 15, iou_threshold: float = 0.3):
        self.next_track_id = 0
        self.tracked_faces: Dict[int, TrackedFace] = OrderedDict()
        self.max_disappeared = max_disappeared
        self.iou_threshold = iou_threshold

    def update(self, detected_faces: List[Dict[str, Any]]) -> List[TrackedFace]:
        """
        Takes list of detected faces in the current frame:
        [{"bbox": (x, y, w, h), "identity": "STU101", "confidence": 0.92, ...}]
        Returns active tracked faces.
        """
        if len(detected_faces) == 0:
            for track_id in list(self.tracked_faces.keys()):
                self.tracked_faces[track_id].disappeared += 1
                if self.tracked_faces[track_id].disappeared > self.max_disappeared:
                    del self.tracked_faces[track_id]
            return list(self.tracked_faces.values())

        if len(self.tracked_faces) == 0:
            for det in detected_faces:
                self._register(
                    det["bbox"],
                    det.get("identity"),
                    det.get("confidence", 0.0),
                    landmarks=det.get("landmarks"),
                    liveness_info=det.get("liveness")
                )
            return list(self.tracked_faces.values())

        # Match existing tracked faces with detected boxes via IoU
        existing_ids = list(self.tracked_faces.keys())
        existing_boxes = [self.tracked_faces[tid].bbox for tid in existing_ids]
        input_boxes = [det["bbox"] for det in detected_faces]

        # Calculate IoU matrix
        iou_matrix = np.zeros((len(existing_boxes), len(input_boxes)), dtype="float32")
        for i, eb in enumerate(existing_boxes):
            for j, ib in enumerate(input_boxes):
                iou_matrix[i, j] = calculate_iou(eb, ib)

        # Greedy match based on maximum IoU
        matched_existing = set()
        matched_input = set()

        if iou_matrix.size > 0:
            rows = iou_matrix.max(axis=1).argsort()[::-1]
            for row in rows:
                col = iou_matrix[row].argmax()
                if iou_matrix[row, col] >= self.iou_threshold and col not in matched_input:
                    track_id = existing_ids[row]
                    det = detected_faces[col]
                    self.tracked_faces[track_id].update(
                        det["bbox"],
                        det.get("identity"),
                        det.get("confidence", 0.0),
                        landmarks=det.get("landmarks"),
                        liveness_info=det.get("liveness")
                    )
                    matched_existing.add(row)
                    matched_input.add(col)

        # Handle unmatched existing tracks
        for row, track_id in enumerate(existing_ids):
            if row not in matched_existing:
                self.tracked_faces[track_id].disappeared += 1
                if self.tracked_faces[track_id].disappeared > self.max_disappeared:
                    del self.tracked_faces[track_id]

        # Handle new detections
        for col, det in enumerate(detected_faces):
            if col not in matched_input:
                self._register(
                    det["bbox"],
                    det.get("identity"),
                    det.get("confidence", 0.0),
                    landmarks=det.get("landmarks"),
                    liveness_info=det.get("liveness")
                )

        return list(self.tracked_faces.values())

    def _register(self, bbox: Tuple[int, int, int, int], identity: Optional[str], confidence: float, landmarks: Optional[np.ndarray] = None, liveness_info: Optional[Dict[str, Any]] = None):
        tf = TrackedFace(self.next_track_id, bbox, identity, confidence, landmarks=landmarks)
        if liveness_info:
            tf.is_live = liveness_info.get("is_live", True)
            tf.liveness_reason = liveness_info.get("reason", "Evaluating...")
            tf.liveness_score = liveness_info.get("texture_score", 1.0)
            if not tf.is_live:
                tf.consecutive_spoof_frames = 1
        self.tracked_faces[self.next_track_id] = tf
        self.next_track_id += 1
