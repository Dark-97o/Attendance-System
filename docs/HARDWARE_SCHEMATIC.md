# HARDWARE SCHEMATIC & WIRING SPECIFICATION

**Project:** AI-Based Face Detection Attendance System  
**Target SBC:** Raspberry Pi 5 (4GB / 8GB)  
**Primary Sensors:** R307 Optical Fingerprint Module & Night Vision Camera  
**Display:** Official Raspberry Pi 7-Inch Touchscreen (DSI) / HDMI Touch Display  

---

## 1. COMPONENT BILL OF MATERIALS (BOM)

| Component | Specification / Model | Interface | Operating Voltage |
|:----------|:----------------------|:----------|:-----------------:|
| **Single Board Computer** | Raspberry Pi 5 (Quad Cortex-A76 @ 2.4GHz) | 40-Pin Header, CSI, DSI | 5.1V / 5.0A (USB-C PD) |
| **Fingerprint Sensor** | R307 Optical Fingerprint Scanner | UART (TTL) | 3.3V / 5.0V (VCC), 3.3V Logic |
| **Camera Module** | Pi Camera Module 3 NoIR / Night Vision IR USB | CSI-2 Ribbon or USB 3.0 | 3.3V (CSI) / 5.0V (USB) |
| **Touchscreen Display** | 7-Inch Capacitive Touchscreen (800x480) | 15-pin/22-pin DSI Ribbon | 5.0V (from Pi 40-pin) |
| **Cooling** | Official Raspberry Pi 5 Active Cooler | 4-Pin Fan Header | 5.0V PWM |
| **Power Supply** | Official 27W USB-C Power Adapter | USB Type-C PD | 5.1V @ 5.0A |

---

## 2. R307 OPTICAL FINGERPRINT SENSOR WIRING TABLE

The R307 optical fingerprint scanner features a 6-pin JST connector (pitch 1.0mm or 1.25mm). Connect the wire leads to the Raspberry Pi 5 40-pin GPIO header as follows:

| Pin # | R307 Wire Color | R307 Signal | Raspberry Pi 5 Header Pin | RPi 5 Pin Name | Description / Notes |
|:-----:|:---------------:|:-----------:|:-------------------------:|:---------------|:--------------------|
| **1** | **Red**         | **VCC**     | **Pin 1 or Pin 2**        | **3.3V / 5.0V**| Power supply (5V or 3.3V supported) |
| **2** | **Black**       | **GND**     | **Pin 6 or Pin 9**        | **Ground**     | Common system ground |
| **3** | **Yellow**      | **TXD**     | **Pin 10 (GPIO 15)**      | **UART0 RXD**  | Sensor transmit $\rightarrow$ Pi receive |
| **4** | **White / Green**| **RXD**    | **Pin 8 (GPIO 14)**       | **UART0 TXD**  | Sensor receive $\leftarrow$ Pi transmit |
| **5** | **Blue**        | **Touch Out**| **Pin 12 (GPIO 18)**     | **GPIO 18**    | *Optional:* Finger detection wake-up |
| **6** | **Orange**      | **Touch VCC**| **Pin 1 (3.3V)**         | **3.3V**       | *Optional:* Power for touch circuit |

> [!IMPORTANT]
> **Logic Level Warning:** The Raspberry Pi 5 GPIO pins operate strictly at **3.3V CMOS logic**. Never expose GPIO 15 (RXD) to 5V. When powering R307 from 5V, ensure the R307 TX pin outputs 3.3V TTL (standard on R307/R308 revisions), or power R307 directly from Pi 5's **Pin 1 (3.3V Power)**.

---

## 3. RASPBERRY PI 5 40-PIN HEADER DIAGRAM

```
                         3.3V Power  (01) [X] [X] (02)  5V Power (Display / R307 VCC)
        SDA1 / GPIO 2 (I2C1 Data)   (03) [ ] [X] (04)  5V Power
       SCL1 / GPIO 3 (I2C1 Clock)   (05) [ ] [X] (06)  Ground (R307 GND)
                  GPIO 4 (GPCLK0)   (07) [ ] [X] (08)  GPIO 14 (UART0 TXD -> R307 RXD)
                           Ground   (09) [X] [X] (10)  GPIO 15 (UART0 RXD <- R307 TXD)
            GPIO 17 (Touch Interrupt)(11) [ ] [X] (12)  GPIO 18 (R307 Touch Out)
                          GPIO 27   (13) [ ] [X] (14)  Ground
                          GPIO 22   (15) [ ] [ ] (16)  GPIO 23
                       3.3V Power   (17) [ ] [ ] (18)  GPIO 24
            GPIO 10 (SPI0 MOSI)     (19) [ ] [X] (20)  Ground
             GPIO 9 (SPI0 MISO)     (21) [ ] [ ] (22)  GPIO 25
            GPIO 11 (SPI0 SCLK)     (23) [ ] [ ] (24)  GPIO 8 (SPI0 CE0)
                           Ground   (25) [ ] [ ] (26)  GPIO 7 (SPI0 CE1)
                            ...     ...  ... ... ...   ...
```

---

## 4. CAMERA & DISPLAY CONNECTIONS

### 4.1 Night Vision IR Camera (CSI-2 Connection)
1. On the Raspberry Pi 5, locate the dual 4-lane MIPI CSI/DSI connectors (`CAM/DISP0` and `CAM/DISP1`). Note that Pi 5 uses high-density 22-pin 0.5mm pitch FPC connectors.
2. If using a standard 15-pin Pi Camera ribbon, connect using a **15-pin to 22-pin adapter ribbon cable**.
3. Insert the ribbon with silver contacts facing towards the HDMI ports.

### 4.2 7-Inch Touchscreen (DSI Ribbon Connection)
1. Connect the DSI ribbon to the second connector (`CAM/DISP1`).
2. Power the display backlight by connecting the display's 5V and GND jumper wires to Raspberry Pi 5 **Pin 2 (5V)** and **Pin 6 (GND)**.

---

## 5. RASPBERRY PI OS CONFIGURATION INSTRUCTIONS

To activate the physical hardware UART for the R307 sensor on Raspberry Pi 5:

1. Edit `/boot/firmware/config.txt` (or `/boot/config.txt` on older OS releases):
   ```bash
   sudo nano /boot/firmware/config.txt
   ```
2. Add the following lines to enable UART0 and disable Bluetooth UART conflict:
   ```ini
   # Enable primary hardware UART for R307 Fingerprint Module
   enable_uart=1
   dtoverlay=disable-bt
   ```
3. Disable Linux serial console on `ttyAMA0` so serial data is not interpreted as shell commands:
   ```bash
   sudo raspi-config
   # Select: Interface Options -> Serial Port
   # "Would you like a login shell over serial?" -> NO
   # "Would you like serial port hardware enabled?" -> YES
   ```
4. Reboot the Raspberry Pi 5:
   ```bash
   sudo reboot
   ```
5. Verify that `/dev/ttyAMA0` or `/dev/serial0` is created:
   ```bash
   ls -l /dev/serial*
   ```
