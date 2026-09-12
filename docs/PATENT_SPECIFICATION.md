# PATENT SPECIFICATION

**TITLE OF THE INVENTION:**  
DUAL-BIOMETRIC EDGE COMPUTING ATTENDANCE SYSTEM WITH HARDWARE-GATED TEMPORAL HYSTERESIS FILTERING AND ADAPTIVE LUMINANCE COMPENSATION FOR CLASSROOM ENVIRONMENTS

**INVENTOR(S):**  
[Insert Inventor Names]

---

## 1. ABSTRACT
A dual-biometric edge-computing system and method for autonomous, tamper-resistant classroom attendance monitoring running entirely on a low-power single-board computer (Raspberry Pi 5). The system integrates a primary biometric gating subsystem comprising an optical fingerprint sensor (R307) operating over a universal asynchronous receiver-transmitter (UART) interface, and a secondary biometric subsystem comprising a multi-face detection and identification edge vision pipeline. Face logging is strictly and cryptographically disabled until an authorized instructor authenticates via the primary fingerprint sensor to establish an active lecture session. A low-compute image preprocessor dynamically executes Contrast Limited Adaptive Histogram Equalization (CLAHE) on the luminance (L) channel of the CIELAB color space coupled with adaptive gamma correction to normalize poor classroom and infrared night-vision lighting. A multi-face spatial Intersection-over-Union (IoU) tracker and a temporal dwell-time hysteresis state machine prevent duplicate registrations, false positives from transitory passersby, and facial jitter. Real-time telemetry, live video overlays, and historical attendance trends are rendered on an integrated 7-inch capacitive touchscreen.

---

## 2. FIELD OF THE INVENTION
The present invention relates generally to automated biometric identification, edge computing, and smart classroom administration. More particularly, the invention relates to an autonomous, edge-deployed dual-biometric system wherein high-speed continuous facial recognition attendance is temporally and programmatically gated by physical instructor fingerprint authentication, featuring low-light compensation and hysteresis filtering optimized for resource-constrained ARM Cortex-A76 microarchitectures.

---

## 3. BACKGROUND OF THE INVENTION & PRIOR ART LIMITATIONS
Conventional automated classroom attendance systems suffer from several fundamental technological and architectural deficiencies:

1. **Vulnerability to False / Fraudulent Attendance:** Continuous facial recognition systems scan any faces within camera range, frequently logging students who are merely walking past the classroom doorway, waiting outside before a lecture begins, or present during unauthorized hours.
2. **Cloud Dependency and Network Latency:** Existing commercial systems transmit video streams across wide area networks (WAN) to cloud servers for inferencing. This introduces substantial bandwidth consumption, recurring subscription costs, and severe biometric privacy risks.
3. **Environmental and Lighting Degradation:** Classroom environments exhibit extreme lighting variability (e.g., blinds drawn, overhead fluorescent lights extinguished during multimedia projector presentations, or infrared night-vision illumination). Conventional facial recognition engines experience substantial accuracy degradation in sub-50 lux conditions.
4. **Compute Bottlenecks on Edge SBCs:** Running multiple high-dimensional deep neural networks concurrently on low-power edge processors results in thermal throttling, frame dropping, and unacceptable processing latency.
5. **Absence of Instructor Gating:** Conventional systems lack an intrinsic physical hardware interlock tying attendance session validity to instructor presence.

There is an acute need for a self-contained, low-cost edge system that combines physical instructor fingerprint authentication with robust facial recognition, edge-optimized lighting compensation, and anti-duplicate hysteresis filtering.

---

## 4. DETAILED DESCRIPTION OF PREFERRED EMBODIMENTS

### 4.1 System Hardware Architecture
Referring to **Figure 1**, the edge attendance appliance comprises:
- **Central Compute Unit:** Raspberry Pi 5 single-board computer featuring a Broadcom BCM2712 SoC with a quad-core 64-bit ARM Cortex-A76 processor clocked at 2.4 GHz, 4GB/8GB LPDDR4X SDRAM, and a VideoCore VII GPU.
- **Primary Biometric Interlock:** R307 Optical Fingerprint Sensor Module coupled via 3.3V UART (GPIO 14 TXD0, GPIO 15 RXD0) operating at 57,600 baud. The sensor incorporates an onboard DSP processor, high-precision optical prism, 500 DPI imaging matrix, and internal Flash memory storing up to 300 biometric minutiae templates.
- **Vision Ingestion Subsystem:** A 1080p night-vision infrared camera module interfaced via CSI-2 (Camera Serial Interface) or USB 3.0 V4L2.
- **Human-Machine Interface:** A 7-inch DSI capacitive touchscreen display (800x480 / 1024x600 resolution) providing kiosk-mode visual telemetry.

```
       +--------------------------------------------------------+
       |                Raspberry Pi 5 (Edge SBC)               |
       |  Broadcom BCM2712 Quad Cortex-A76 (2.4 GHz)            |
       +---------------------------+----------------------------+
                 | UART (3.3V)     | CSI-2 / USB 3.0      | DSI Ribbon
                 v                 v                      v
     +---------------------+ +------------------+ +-----------------+
     | R307 Optical Sensor | | Night IR Camera  | | 7" Touchscreen  |
     | (Fingerprint Gating)| | (Classroom Feed) | | (Live Kiosk UI) |
     +---------------------+ +------------------+ +-----------------+
```

### 4.2 Primary Biometric Authentication & Session Gating Mechanism
Attendance logging is strictly governed by a finite state machine:
1. **Quiescent State ($S_{\text{idle}}$):** The camera continuously captures frames for preview, but all attendance recording databases and logging queues are locked.
2. **Authentication State:** An instructor places their finger upon the R307 optical prism. The R307 executes:
   - Packet Header: `0xEF01`
   - Command: `0x01` (`GenImg`) $\rightarrow$ Finger detected.
   - Command: `0x02` (`Img2Tz`) $\rightarrow$ Minutiae character file generated.
   - Command: `0x04` (`Search`) $\rightarrow$ Fast $O(1)$ onboard template matching.
3. **Session Activation ($S_{\text{active}}$):** Upon confirmation code `0x00`, the instructor's identifier is verified against the local SQLite database. A unique session record ($SES\_ID$) is instantiated with timestamp $T_{\text{start}}$, unlocking the student attendance logging pipeline.
4. **Session Termination:** A subsequent authorized instructor fingerprint scan automatically terminates the session, sets $T_{\text{end}}$, computes student dwell times, and locks attendance logging.

### 4.3 Low-Light & Infrared CLAHE Preprocessing Pipeline
To guarantee robust face detection under projector darkness or IR night illumination, each video frame $I_{\text{BGR}} \in \mathbb{R}^{H \times W \times 3}$ is transformed:
1. Convert $I_{\text{BGR}}$ to CIELAB color space: $I_{\text{LAB}} = \text{cvtColor}(I_{\text{BGR}}, \text{BGR2LAB})$.
2. Extract the Luminance channel $L \in [0, 255]$.
3. Apply Contrast Limited Adaptive Histogram Equalization (CLAHE) with clip limit $\beta = 3.0$ and grid size $8 \times 8$:
   $$\hat{L} = \text{CLAHE}(L, \beta=3.0, \text{grid}=(8,8))$$
4. Measure mean scene luminance $\mu_L = \frac{1}{HW}\sum_{x,y} L(x,y)$.
5. If $\mu_L < 75.0$ (dark classroom), compute dynamic gamma coefficient:
   $$\gamma = \max\left(0.45, 0.45 + \frac{\mu_L}{75.0} \times 0.55\right)$$
   and apply the nonlinear transformation:
   $$L_{\text{enhanced}}(x,y) = 255 \times \left(\frac{\hat{L}(x,y)}{255}\right)^{1/\gamma}$$
6. Recombine $(L_{\text{enhanced}}, A, B)$ and convert back to BGR space.

### 4.4 Centroid IoU Tracking & Temporal Hysteresis Filter
To eliminate spurious false-positive detections and duplicate logging:
1. **Multi-Scale Face Detection:** Applied every $k$-th frame ($k=2$ or $3$) to conserve Cortex-A76 compute cycles.
2. **Spatial IoU Association:** For existing track $T_i$ with bounding box $B_i$ and detection $D_j$ with bounding box $B_j$:
   $$\text{IoU}(B_i, B_j) = \frac{\text{Area}(B_i \cap B_j)}{\text{Area}(B_i \cup B_j)}$$
3. **Temporal Dwell Threshold:** A student $S_k$ is only marked `PRESENT` if:
   $$N_{\text{consecutive\_frames}}(S_k) \ge \Theta_{\text{dwell}} \quad (\text{where } \Theta_{\text{dwell}} = 3 \text{ frames})$$
   and the cosine similarity score satisfies:
   $$\text{Sim}(\mathbf{u}_{S_k}, \mathbf{v}_{\text{enrolled}}) \ge 0.65$$
4. **Debounce Hysteresis:** Once marked present, timestamp $T_{\text{entry}}$ is fixed. Subsequent recognitions update $T_{\text{last\_seen}}$ and $T_{\text{exit}}$ while suppressing duplicate database writes and WebSocket broadcast alerts within a cooldown interval $\tau_{\text{debounce}} = 20.0\text{ seconds}$.

---

## 5. PATENT CLAIMS

**WE CLAIM:**

1. An edge-computing biometric attendance system, comprising:
   - a single-board computer comprising a multi-core processor, a non-volatile memory, and a hardware serial communication bus;
   - an optical fingerprint sensor operatively connected to said hardware serial communication bus;
   - a digital image capture sensor operatively coupled to said single-board computer; and
   - an edge software pipeline stored in said memory, executable by said multi-core processor, configured to:
     - maintain an attendance logging engine in a locked quiescent state;
     - transition said attendance logging engine to an unlocked active session state strictly upon verifying an authorized instructor fingerprint via said optical fingerprint sensor;
     - continuously acquire digital video frames from said digital image capture sensor during said active session state;
     - detect human facial regions within said video frames;
     - extract numerical biometric feature representations from said detected facial regions;
     - compare said extracted feature representations against a local database of enrolled student templates; and
     - record a verified attendance entry for identified students into a relational database stored in said non-volatile memory only while said active session state persists.

2. The system of claim 1, wherein said single-board computer is a Raspberry Pi 5 comprising a Broadcom BCM2712 quad-core ARM Cortex-A76 processor operating at 2.4 GHz.

3. The system of claim 1, wherein said optical fingerprint sensor is an R307 optical fingerprint scanner communicating with said single-board computer via UART protocol packets having a two-byte synchronization header `0xEF01`.

4. The system of claim 1, wherein transitioning from said active session state to said locked quiescent state is initiated by a subsequent authorized fingerprint scan from said instructor, causing said processor to compute total session duration and individual student dwell times.

5. The system of claim 1, wherein said edge software pipeline comprises an adaptive lighting normalizer configured to convert input video frames to CIELAB color space, apply Contrast Limited Adaptive Histogram Equalization (CLAHE) to the Luminance (L) channel, and dynamically modulate pixel intensities using an adaptive gamma transformation when average scene luminance falls below a predetermined darkness threshold.

6. The system of claim 1, wherein said edge software pipeline comprises a spatial Intersection-over-Union (IoU) multi-face tracker configured to assign persistent track identifiers to detected faces across consecutive video frames.

7. The system of claim 6, wherein said edge software pipeline enforces a temporal dwell-time hysteresis condition requiring a candidate student face to maintain a persistent track identifier with a recognition confidence exceeding a threshold value $\tau \ge 0.65$ for at least three consecutive frames before committing an attendance record to said relational database.

8. The system of claim 1, wherein said relational database is a local SQLite database configured with foreign key enforcement and write-ahead logging (WAL) mode, executing locally on said single-board computer without requiring external cloud network connectivity.

9. The system of claim 1, further comprising a capacitive touchscreen display displaying a real-time kiosk dashboard comprising an annotated video feed overlay, real-time student presence counters, instructor session duration timers, and a virtual fingerprint authentication touch pad.

10. A computer-implemented method for autonomous edge attendance verification, comprising the steps of:
    - detecting an instructor authentication event via an optical fingerprint scanner connected over a physical UART serial interface of a single-board computer;
    - instantiating a lecture session record in a local edge database upon successful fingerprint authentication;
    - processing video frames from a classroom camera feed through an adaptive luminance CLAHE enhancement filter;
    - detecting facial bounding boxes within said enhanced video frames;
    - matching extracted face embeddings against pre-enrolled student feature vectors using cosine distance similarity;
    - applying an anti-duplicate debounce filter with a minimum temporal dwell-time threshold; and
    - logging entry time, last seen time, and match confidence for identified students in said edge database strictly while said lecture session record remains active.
