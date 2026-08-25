# Hardware IoT - AI Traffic Management System
SRM Institute of Science & Technology
Amit Chauhan (RA2311004010332) | Lakshita
Guide: Dr. Bharathababu K

---

## Components Used

| Component | Qty | Purpose |
|---|---|---|
| Raspberry Pi 4 Model B (4GB) | 1 | Main edge computing controller |
| RGB LEDs (Red, Yellow, Green) | 12 | Traffic signal simulation (3 per lane) |
| IR Proximity Sensors (FC-51) | 4 | Lane vehicle density detection |
| Breadboard (full-size) | 1 | Circuit prototyping |
| Jumper Wires (M-M, M-F) | ~60 | GPIO connections |
| USB Camera / Pi Camera | 1 | Live vehicle/ambulance feed |
| HDMI Display | 1 | Live dashboard output |
| 5V/3A USB-C Power Supply | 1 | RPi power |
| Black foam board + chart paper | - | Road intersection model |

---

## GPIO Pin Mapping (BCM)

### Traffic Signal LEDs
| Lane | Red | Yellow | Green |
|---|---|---|---|
| North | GPIO 17 | GPIO 27 | GPIO 22 |
| South | GPIO 5 | GPIO 6 | GPIO 13 |
| East | GPIO 19 | GPIO 26 | GPIO 21 |
| West | GPIO 12 | GPIO 16 | GPIO 20 |

### IR Sensors (Input, Pull-up)
| Sensor | GPIO Pin |
|---|---|
| North IR | GPIO 18 |
| South IR | GPIO 23 |
| East IR | GPIO 24 |
| West IR | GPIO 25 |

---

## Firmware Files

| File | Description |
|---|---|
| traffic_system.py | Main RL-driven controller - fetches state from sensors, runs Q-learning, controls LEDs |
| traffic_final.py | Full integrated version - weather API, ambulance detection, emergency override |

---

## Running on Raspberry Pi

  pip install flask requests RPi.GPIO ultralytics opencv-python-headless
  python traffic_final.py
  # Access dashboard: http://<raspberry-pi-ip>:5000

---

## Network Dashboard Features
- Live IR sensor readings per lane
- Real-time LED state (Red / Yellow / Green)
- Q-learning agent episode / epsilon / reward
- Emergency vehicle override status
- Weather-aware phase duration (Open-Meteo API)
- Real-time power consumption estimate

---

See project_images/ folder for labelled hardware demo photos.
