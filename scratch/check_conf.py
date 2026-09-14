import sys, os
sys.path.insert(0, '.')
import cv2, numpy as np
from engine.face_engine import FaceEngine
from database.models import DatabaseManager

db = DatabaseManager('data/attendance_system.db')
fe = FaceEngine(db)

for sid, meta in fe.student_metadata.items():
    p = meta.get('photo_path')
    name = meta.get('name')
    if p and os.path.exists(p):
        img = cv2.imread(p)
        faces = fe.detect_faces_and_landmarks(img)
        print(f"Student: {sid} ({name}) -> Faces detected in photo: {len(faces)}")
        if faces:
            bbox, lm = faces[0]
            crop = img[bbox[1]:bbox[1]+bbox[3], bbox[0]:bbox[0]+bbox[2]]
            emb = fe.extract_face_embedding(crop, landmark_face=lm, full_image=img)
            sid_match, conf, m = fe.identify_face(emb)
            print(f"   Identified as: {sid_match} ({m['name'] if m else 'Unknown'}), Conf: {conf}")
