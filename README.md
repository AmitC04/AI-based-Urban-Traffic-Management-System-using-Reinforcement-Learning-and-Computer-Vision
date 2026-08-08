<div align="center">

# 🚦 AI-Based Urban Traffic Management System

### Reinforcement Learning + Computer Vision for Adaptive Smart City Traffic Control

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-00FFAA?style=flat-square)](https://ultralytics.com/)
[![TensorFlow](https://img.shields.io/badge/TensorFlow-2.x-FF6F00?style=flat-square&logo=tensorflow&logoColor=white)](https://tensorflow.org/)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-IoT-C51A4A?style=flat-square&logo=raspberrypi&logoColor=white)](https://raspberrypi.org/)

> A real-time, AI-powered traffic signal controller combining **Deep Q-Network (DQN) Reinforcement Learning** and **YOLOv8 Computer Vision** to adaptively optimize urban intersection throughput, prioritize emergency vehicles, protect pedestrians, and respond to weather conditions. Deployed on both a full-stack Flask web application and a physical **Raspberry Pi IoT** model.

---

</div>

## 📸 Project Gallery

<table>
  <tr>
    <td align="center">
      <img src="02_HARDWARE_IOT/project_images/hardware_02_iot_model_top_view_with_cars.jpg" width="400" alt="IoT Model Top View"/>
      <br><sub><b>IoT Model — 4-Way Intersection (Top View)</b></sub>
    </td>
    <td align="center">
      <img src="03_DOCS/media/screenshots/software_01_dashboard_live_screen.jpg" width="400" alt="Live Dashboard"/>
      <br><sub><b>Software — Live AI Dashboard (4 Lanes)</b></sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <img src="02_HARDWARE_IOT/project_images/hardware_04_iot_full_intersection_top.jpg" width="400" alt="Full Intersection"/>
      <br><sub><b>IoT Model — Full Intersection with Sensors</b></sub>
    </td>
    <td align="center">
      <img src="03_DOCS/media/screenshots/software_02_raspberry_pi_dashboard.jpg" width="400" alt="RPi Dashboard"/>
      <br><sub><b>Software — Raspberry Pi Live Control Dashboard</b></sub>
    </td>
  </tr>
</table>

## 📋 Overview

**AI-UTMS** uses a **Deep Q-Network (DQN) Reinforcement Learning agent** trained on an 18-dimensional state space to make adaptive, real-time signal decisions. A **YOLOv8 Computer Vision pipeline** provides live vehicle detection, ambulance identification, and pedestrian recognition across all 4 lanes.

### Why this approach is different

| Traditional Fixed Timers | AI-UTMS (RL + CV) |
|---|---|
| Fixed green time regardless of traffic | Adaptive green time based on real-time density |
| No emergency vehicle awareness | YOLOv8 detects ambulances → instant override |
| No weather consideration | Weather factor adjusts green duration |

## 🚀 Installation (Software)

### Step 1: Clone the Repository
```bash
git clone https://github.com/AmitC04/AI-based-Urban-Traffic-Management-System-using-Reinforcement-Learning-and-Computer-Vision.git
cd AI-based-Urban-Traffic-Management-System-using-Reinforcement-Learning-and-Computer-Vision/itms_rl
```

### Step 2: Set Up Virtual Environment
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Step 3: Launch the Dashboard
```bash
python app.py
```
On first run, go to `/signup` to create your account.

## 👨‍💻 Project Team

**Minor Project — SRM Institute of Science & Technology**
Dept. of Electronics and Communication Engineering

| Name | Role | GitHub |
|---|---|---|
| **Amit Chauhan** | Lead Developer — RL Agent, Backend, IoT | [@AmitC04](https://github.com/AmitC04) |
| **Lakshita** | Hardware Integration, Dataset, Testing | [@lakshita4816](https://github.com/lakshita4816) |

**Faculty Guide:** Dr. Bharathababu K — Dept. of ECE, SRMIST
