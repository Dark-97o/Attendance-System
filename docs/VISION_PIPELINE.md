# Vision & Biometric Pipeline Architecture

The Attendance System implements a multi-stage face processing pipeline optimized for edge CPU inference:

```
[Camera Feed / RTSP]
       │
       ▼
[YuNet Face Detector (ONNX)] ──► 5 Facial Landmarks + Bounding Box
       │
       ▼
[Affine Alignment Matrix (112x112 chip)]
       │
       ▼
[Anti-Spoofing & Liveness Guard]
   ├── 1. Laplacian Texture Variance (> 85.0)
   ├── 2. Multi-frame EAR Blink Detector
   └── 3. Frequency Domain Moiré Filter
       │
       ▼
[SFace Deep Embedding Network (ONNX)] ──► 128-D Feature Vector
       │
       ▼
[Vectorized Cosine Matcher (In-Memory Cache)] ──► Student / Faculty Match
```

## Latency Profile on Modern x86 CPU
| Stage | Avg Duration | Method |
|---|---|---|
| YuNet Detection | 12.4 ms | ONNX Runtime CPU |
| Affine Landmark Alignment | 1.1 ms | OpenCV WarpAffine |
| Multi-Layer Liveness Check | 4.2 ms | NumPy Vectorized |
| SFace 128D Embedding Extraction | 14.8 ms | ONNX Runtime CPU |
| In-Memory Cosine Vector Match | 0.3 ms | Dot Product against 500 vectors |
| **Total Turnaround** | **~32.8 ms** | **~30 FPS real-time throughput** |
