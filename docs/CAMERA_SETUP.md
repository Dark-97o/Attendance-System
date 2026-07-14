# Camera Hardware Setup & Configuration

## Recommended Hardware
- **Primary Biometric Camera**: 1080p 60fps USB Video Class (UVC) webcam with Wide Dynamic Range (WDR).
- **USB Interface**: USB 3.0 controller port to avoid frame tearing under low latency DirectShow streaming.

## Windows DirectShow Configuration
The system uses OpenCV with `cv2.CAP_DSHOW` on Windows:
```python
cap = cv2.VideoCapture(device_index, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
```

## Multi-Camera Switching
The backend diagnostics endpoint dynamically enumerates available device indices (`0`, `1`, `2`) and caches valid indices for 60 seconds to eliminate capture initialization lag.
