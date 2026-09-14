import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2
import numpy as np
from database.models import DatabaseManager
from engine.face_engine import FaceEngine

db = DatabaseManager('data/attendance_system.db')
fe = FaceEngine(db)

cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
ret, frame = cap.read()
cap.release()
print('Camera 1 read:', ret)
if ret:
    cv2.imwrite('scratch/usb_cam_frame.jpg', frame)
    print(f'Saved frame of shape: {frame.shape}, mean brightness: {np.mean(frame):.1f}')
    faces = fe.detect_faces_and_landmarks(frame)
    print('Detected faces count:', len(faces))
    for i, (bbox, lm) in enumerate(faces):
        x, y, w, h = bbox
        print(f'Face {i}: bbox={bbox}')
        emb = fe.extract_face_embedding(frame[y:y+h, x:x+w], landmark_face=lm, full_image=frame)
        print("Similarity scores:")
        for sid, tmpls in fe.enrolled_cache.items():
            name = fe.student_metadata[sid]["name"]
            sims = [float(np.dot(emb, t)) for t in tmpls]
            print(f'  {sid} ({name}): max={max(sims):.3f}')
        ident_sid, conf, meta = fe.identify_face(emb)
        print(f'  ==> Result: {ident_sid} ({meta["name"] if meta else "None"}), conf={conf}')
else:
    print("Failed to capture from Camera 1")
