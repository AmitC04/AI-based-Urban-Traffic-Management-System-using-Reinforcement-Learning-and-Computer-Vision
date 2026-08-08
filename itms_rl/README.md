# ­ƒÜª AI-based Urban Traffic Management System
### Reinforcement Learning + Computer Vision
**SRM Institute of Science & Technology**
Amit Chauhan (RA2311004010332) | Shaily Giri | Lakshita
Guide: Dr. Bharathababu K

---

## ­ƒåò Upgrades from v1 (YOLOv8-only)

| Feature | v1 (Old) | v2 (This) |
|---------|----------|-----------|
| Signal decision | Density formula | **DQN Reinforcement Learning** |
| Pedestrian detection | ÔØî | **Ô£à YOLOv8 (COCO class 0)** |
| Weather awareness | ÔØî | **Ô£à Weather state + green time extension** |
| RL training monitor | ÔØî | **Ô£à Live reward/loss/epsilon charts** |
| Decision modes | 1 | **5 (exploit, explore, ambulance, pedestrian, starvation guard)** |
| Starvation prevention | ÔØî | **Ô£à Cycle guard after 4 skips** |
| DB logging | Basic | **+ pedestrian count + decision mode** |

---

## ­ƒôü Structure

```
itms_rl/
Ôö£ÔöÇÔöÇ app.py                   # Flask routes
Ôö£ÔöÇÔöÇ detector.py              # YOLOv8 detector + simulation fallback
Ôö£ÔöÇÔöÇ traffic_logic.py         # RL-driven signal controller (threading)
Ôö£ÔöÇÔöÇ rl_agent/
Ôöé   ÔööÔöÇÔöÇ dqn_agent.py         # DQN agent (TF 2.x)
Ôö£ÔöÇÔöÇ models/
Ôöé   ÔööÔöÇÔöÇ dqn_traffic.weights.h5  # Saved weights (auto-created)
Ôö£ÔöÇÔöÇ templates/
Ôöé   Ôö£ÔöÇÔöÇ login.html
Ôöé   Ôö£ÔöÇÔöÇ project_home.html
Ôöé   Ôö£ÔöÇÔöÇ upload.html
Ôöé   Ôö£ÔöÇÔöÇ dashboard.html       # Live 4-lane + weather + pedestrian
Ôöé   Ôö£ÔöÇÔöÇ rl_monitor.html      # Live RL training charts
Ôöé   ÔööÔöÇÔöÇ analysis.html        # Stats + decision mode donut
Ôö£ÔöÇÔöÇ uploads/
ÔööÔöÇÔöÇ requirements.txt
```

---

## ÔÜÖ´©Å Setup

```bash
pip install -r requirements.txt
python app.py
# Open: http://127.0.0.1:5000
# First run: create account at /signup (first account becomes admin)
```

**TensorFlow optional** ÔÇö if not installed, agent falls back to rule-based logic and all other features still work.

**Emergency model note** ÔÇö you can either:
1. place `best.pt` in the project root, or
2. upload a `.pt` emergency model from the Upload page (saved as `models/emergency_best.pt`).

If no emergency model is available, the app uses heuristic fallback (works, but less accurate).
Default emergency runtime is now **Custom Model Only** with **0.70 confidence** for higher precision.
Heuristic fallback is no longer default.

When an emergency detection overlaps a normal vehicle detection, the final label is forced to
`AMBULANCE` / `POLICE` / `FIRE` (not Car/Bus/Truck).

Custom emergency labels are restricted to emergency-only classes:
- `ambulance`
- `police`
- `fire` / `firebrigade` / `firetruck`

---

## ­ƒÜæ Train Emergency Model (.pt)

Use the included trainer to build a dedicated emergency detector with higher accuracy than heuristic mode.

### 1) Prepare dataset

Copy `emergency_dataset.yaml.example` to `emergency_dataset.yaml` and set paths.

Required class naming:
- `0: ambulance`
- `1: police`
- `2: fire`

### 2) Train

```bash
python validate_emergency_dataset.py --data emergency_dataset.yaml
python train_emergency_model.py --data emergency_dataset.yaml --epochs 120 --imgsz 960
```


### 3) Output

After training, best checkpoint is copied to:

```bash
models/emergency_best.pt
```

This file is auto-detected by the app at startup or can be replaced via Upload page.

To run app in your high-accuracy setup after model build:

```bash
python app.py
```

---

## ­ƒÄø´©Å Runtime Accuracy Controls

From Dashboard top bar:

- **Emergency Policy**
       - `custom_only` (recommended for highest precision)
       - `hybrid` (custom model + heuristic fallback)
       - `heuristic_only` (least accurate)

- **Emergency Min Conf** (0.30ÔÇô0.95)
       - Recommended: `0.70` or higher for fewer false positives

- **Emergency Sensitivity** (heuristic only)
       - Keep `strict` when using heuristic fallback

---

## ­ƒºá RL State Vector (18-dim)

```
[0:4]   Normalized lane densities
[4:8]   Normalized wait times per lane
[8:12]  Ambulance flags (0/1 per lane)
[12:16] Pedestrian flags (0/1 per lane)
[16]    Weather factor (0=clear, 0.5=rain, 1.0=fog)
[17]    Current green phase (0-3, normalized)
```

## ­ƒÄ» Reward Function

```
reward = wait_delta ├ù 2.0         # main objective
       + 20 if ambulance served   # emergency priority
       + 5  if pedestrian cleared # safety
       + 3  if starvation relief  # fairness
       - 0.1 ├ù density_served     # control cost
```

---

## ­ƒôè Pages

| Route | Description |
|-------|-------------|
| `/` | Login |
| `/signup` | Create account (first account becomes admin) |
| `/home` | Project intro + progress timeline |
| `/upload` | Upload lane videos and optionally enable simulation mode |
| `/dashboard` | Live feeds + signals + weather + RL mode |
| `/rl_monitor` | **NEW** ÔÇö DQN training charts, reward curve, ╬Á-decay |
| `/analysis` | Cumulative stats, decision mode donut, vehicle breakdown |

## ­ƒº¥ Config-driven Timeline

Project timeline entries are loaded from `project_phases.json`.
Update that file to change phases without editing backend code.
