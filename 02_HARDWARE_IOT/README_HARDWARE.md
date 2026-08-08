# ⚡ Hardware & IoT Integration (Raspberry Pi)

## Components List
- **Raspberry Pi 4 Model B (4GB)**
- **RGB LED Modules** (x12, common-cathode)
- **IR Proximity Sensors (FC-51)** (x4)
- **USB Camera / Pi Camera Module** (x1)
- **Power Supply (5V 3A)**
- **Breadboard & Jumper Wires (F-F, M-F)**
- **Intersection Model** (chart paper, foam board, toy cars)

## GPIO Wiring Guide
| Module | Pin 1 (GND) | Pin 2 (Red) | Pin 3 (Yellow) | Pin 4 (Green) |
|---|---|---|---|---|
| **NORTH** | RPi GND | GPIO 17 | GPIO 27 | GPIO 22 |
| **SOUTH** | RPi GND | GPIO 5 | GPIO 6 | GPIO 13 |
| **EAST** | RPi GND | GPIO 19 | GPIO 26 | GPIO 21 |
| **WEST** | RPi GND | GPIO 20 | GPIO 16 | GPIO 12 |

## Running the Firmware
```bash
cd 02_HARDWARE_IOT/firmware
pip install -r ../../itms_rl/requirements.txt
python traffic_final.py
```
