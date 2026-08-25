#!/usr/bin/env python3
"""
AI Traffic Management System — FINAL v2
SRMIST ECE Project
Fixes:
  - Yellow LED: explicit pin-by-pin control, no shortcuts
  - NORTH-G moved: GPIO22 → GPIO4  (22 was causing issues)
  - EAST fully moved: R→GPIO10, Y→GPIO9, G→GPIO7  (19/26/21 bad)
  - IR 23/24/25 kept but now physically away from new LED pins
  - Weather location label: Chennai, Tamil Nadu
"""

import time, threading, random, math, base64, socket
from collections import deque
import cv2
import numpy as np
from flask import Flask, render_template_string, jsonify

try:
    import requests
    REQ_OK = True
except ImportError:
    REQ_OK = False

# ── GPIO ─────────────────────────────────────────────────────────────────
try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO_OK = True
    print("[GPIO] BCM mode OK")
except Exception as e:
    GPIO_OK = False
    print(f"[GPIO] Simulation ({e})")

DIRECTIONS     = ["NORTH", "SOUTH", "EAST", "WEST"]
AMBULANCE_LANE = "NORTH"

# ── UPDATED PIN MAP ──────────────────────────────────────────────────────
# NORTH-G: 22→4   EAST: 19/26/21→10/9/7
LED_PINS = {
    "NORTH": {"R": 17, "Y": 27, "G":  4},   # G moved 22→4
    "SOUTH": {"R":  5, "Y":  6, "G": 13},   # unchanged (working)
    "EAST" : {"R": 10, "Y": 26, "G":  7},   # Y: 9→26(pin37), R: 19→10, G: 21→7
    "WEST" : {"R": 11, "Y": 16, "G": 12},   # R moved 20→11 (prev fix)
}
IR_PINS  = {"NORTH": 23, "SOUTH": 24, "EAST": 25, "WEST": 8}

LED_MW = 35
PI_MW  = 2500

# ── Setup ALL pins immediately after setmode ─────────────────────────────
def gpio_init():
    if not GPIO_OK: return
    for d, pins in LED_PINS.items():
        for c, p in pins.items():
            GPIO.setup(p, GPIO.OUT)
            GPIO.output(p, GPIO.LOW)
    for d, p in IR_PINS.items():
        GPIO.setup(p, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    print("[GPIO] All pins ready")

gpio_init()

# ── Signal control — explicit pin-by-pin, no shortcuts ──────────────────
def _led(pin, on):
    if GPIO_OK:
        GPIO.output(pin, GPIO.HIGH if on else GPIO.LOW)

def set_signal(direction, state):
    """Explicitly set each of the 3 pins — no ambiguity."""
    p = LED_PINS[direction]
    _led(p["R"], state == "RED")
    _led(p["Y"], state == "YELLOW")
    _led(p["G"], state == "GREEN")

def all_red():
    for d in DIRECTIONS:
        set_signal(d, "RED")

def all_off():
    """Turn every LED pin LOW before transitioning."""
    for d in DIRECTIONS:
        for c, p in LED_PINS[d].items():
            _led(p, False)

def read_ir(d):
    if not GPIO_OK: return False
    return GPIO.input(IR_PINS[d]) == GPIO.LOW

def cleanup():
    if GPIO_OK:
        all_off()
        GPIO.cleanup()

all_red()   # safe start state

# ════════════════════════════════════════════════════════════════════════
#  IR MANAGER
# ════════════════════════════════════════════════════════════════════════
class IRManager:
    WIN = 15
    def __init__(self):
        self._wins   = {d: deque([False]*self.WIN, maxlen=self.WIN) for d in DIRECTIONS}
        self._lock   = threading.Lock()
        self.running = False
        self._base   = {d: random.randint(2,8) for d in DIRECTIONS}
        self._tick   = 0

    def _sim(self, d):
        b    = self._base[d]
        n    = math.sin(self._tick*0.08 + DIRECTIONS.index(d)*1.3)*2.5
        prob = max(0.05, min(0.95, (b+n)/10.0))
        return random.random() < prob

    def run(self):
        self.running = True
        while self.running:
            self._tick += 1
            if self._tick % 200 == 0:
                self._base = {d: random.randint(0,9) for d in DIRECTIONS}
            for d in DIRECTIONS:
                val = read_ir(d) if GPIO_OK else self._sim(d)
                with self._lock:
                    self._wins[d].append(val)
            time.sleep(0.2)

    def get_density(self):
        with self._lock:
            return {d: int(sum(self._wins[d])*10//self.WIN) for d in DIRECTIONS}

    def stop(self): self.running = False

# ════════════════════════════════════════════════════════════════════════
#  AMBULANCE DETECTOR
# ════════════════════════════════════════════════════════════════════════
class AmbulanceDetector:
    W_LO = np.array([0,   0, 185], dtype=np.uint8)
    W_HI = np.array([180, 55, 255], dtype=np.uint8)
    AREA = 1400

    def __init__(self):
        self._cap    = self._open()
        self._det    = False
        self._conf   = 0.0
        self._b64    = None
        self._lock   = threading.Lock()
        self.running = False

    def _open(self):
        for bk, src in [(cv2.CAP_V4L2,"/dev/video0"),
                        (cv2.CAP_V4L2,0),(cv2.CAP_ANY,0)]:
            try:
                cap = cv2.VideoCapture(src, bk)
                if cap.isOpened():
                    ret, f = cap.read()
                    if ret and f is not None:
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  320)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
                        cap.set(cv2.CAP_PROP_FPS, 10)
                        print(f"[CAM] {src}")
                        return cap
                cap.release()
            except: pass
        print("[CAM] No camera — simulation mode")
        return None

    def _detect(self, frame):
        hsv  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.W_LO, self.W_HI)
        k    = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)
        area = cv2.countNonZero(mask)
        return area >= self.AREA, min(1.0, area/(self.AREA*3)), mask

    def run(self):
        self.running = True
        while self.running:
            if self._cap:
                ret, frame = self._cap.read()
                if not ret: frame = np.zeros((240,320,3),dtype=np.uint8)
            else:
                frame   = np.full((240,320,3),(20,22,30),dtype=np.uint8)
                sim_det = (int(time.time())%90) < 6
                if sim_det:
                    cv2.rectangle(frame,(125,85),(195,155),(225,225,230),-1)

            det, conf, mask = self._detect(frame)
            vis = frame.copy()
            if mask is not None:
                ov = np.zeros_like(vis)
                ov[mask>0] = [0,220,255]
                vis = cv2.addWeighted(vis,0.75,ov,0.25,0)
            col = (0,255,80) if det else (60,60,100)
            cv2.rectangle(vis,(1,1),(319,239),col,2)
            cv2.rectangle(vis,(0,0),(320,22),(0,0,0),-1)
            cv2.putText(vis,f"{'AMBULANCE DETECTED' if det else 'CLEAR'}  {conf*100:.0f}%",
                (5,15),cv2.FONT_HERSHEY_SIMPLEX,0.45,col,1)
            cv2.rectangle(vis,(0,232),(320,240),(30,30,30),-1)
            bw = int(conf*320)
            cv2.rectangle(vis,(0,232),(bw,240),(0,200,80) if not det else (0,255,80),-1)
            _, j = cv2.imencode(".jpg",vis,[cv2.IMWRITE_JPEG_QUALITY,75])
            b64  = base64.b64encode(j.tobytes()).decode()
            with self._lock:
                self._det  = det
                self._conf = conf
                self._b64  = b64
            time.sleep(0.12)

    def is_ambulance(self):
        with self._lock: return self._det, self._conf

    def get_b64(self):
        with self._lock: return self._b64

    def stop(self):
        self.running = False
        if self._cap: self._cap.release()

# ════════════════════════════════════════════════════════════════════════
#  WEATHER  — Chennai location
# ════════════════════════════════════════════════════════════════════════
class WeatherService:
    # SRM Kattankulathur, Chennai
    URL = ("https://api.open-meteo.com/v1/forecast"
           "?latitude=12.8231&longitude=80.0444"
           "&current_weather=true&forecast_days=1")
    LOCATION = "Chennai, Tamil Nadu"
    WMO = {0:"Clear",1:"Mainly clear",2:"Partly cloudy",3:"Overcast",
           45:"Fog",51:"Light drizzle",61:"Light rain",63:"Rain",
           65:"Heavy rain",80:"Showers",95:"Thunderstorm"}

    def __init__(self):
        self.temperature = 28.0
        self.condition   = "Clear"
        self.wmo_code    = 0
        self.wind_speed  = 0.0
        self.modifier    = 1.0
        self._lock       = threading.Lock()
        self.running     = False

    def _fetch(self):
        if not REQ_OK: return
        try:
            cw   = requests.get(self.URL,timeout=8).json()["current_weather"]
            code = int(cw["weathercode"])
            mod  = 1.4 if code>=65 else (1.2 if code>=51 else 1.0)
            with self._lock:
                self.temperature = float(cw["temperature"])
                self.wind_speed  = float(cw["windspeed"])
                self.wmo_code    = code
                self.condition   = self.WMO.get(code,"Unknown")
                self.modifier    = mod
            print(f"[WX] {self.condition} {self.temperature}°C")
        except Exception as e: print(f"[WX] {e}")

    def run(self):
        self.running = True
        self._fetch()
        while self.running:
            time.sleep(600)
            self._fetch()

    def get(self):
        with self._lock:
            return {"temperature":round(self.temperature,1),
                    "condition":self.condition,"wmo_code":self.wmo_code,
                    "wind_speed":round(self.wind_speed,1),
                    "modifier":round(self.modifier,2),
                    "location":self.LOCATION}

    def stop(self): self.running = False

# ════════════════════════════════════════════════════════════════════════
#  Q-LEARNING AGENT
# ════════════════════════════════════════════════════════════════════════
class RLAgent:
    ACTIONS = {
        0:(["NORTH"], 12), 1:(["NORTH"], 25),
        2:(["SOUTH"], 12), 3:(["SOUTH"], 25),
        4:(["EAST"],  12), 5:(["EAST"],  25),
        6:(["WEST"],  12), 7:(["WEST"],  25),
    }
    def __init__(self):
        self.q       = {}
        self.alpha   = 0.12
        self.gamma   = 0.90
        self.eps     = 0.35
        self.eps_min = 0.05
        self.eps_d   = 0.994
        self.ep      = 0
        self.total   = 0.0
        self.hist    = deque(maxlen=80)

    def _b(self,v): return 0 if v<=2 else (1 if v<=6 else 2)

    def state(self, density):
        return tuple(self._b(density[d]) for d in DIRECTIONS)

    def choose(self, s):
        if random.random() < self.eps or s not in self.q:
            return random.randint(0,7)
        return int(np.argmax(self.q[s]))

    def choose_sequential(self, current_idx, density, wx_mod):
        """
        Sequential with density override.
        current_idx: 0=N,1=S,2=E,3=W — which lane was last green
        Returns (lane_index, duration)
        """
        DIR_ORDER = ["NORTH","SOUTH","EAST","WEST"]

        # Check for HIGH density lane — serve it immediately
        high_lanes = [d for d in DIR_ORDER if density.get(d,0) >= 7]
        if high_lanes:
            # Serve highest density lane
            busiest = max(DIR_ORDER, key=lambda d: density.get(d,0))
            idx = DIR_ORDER.index(busiest)
        else:
            # Normal sequential: next in rotation
            idx = (current_idx + 1) % 4

        lane = DIR_ORDER[idx]
        d_val = density.get(lane, 0)

        # Duration: 12s base + extra based on density, weather modifier
        base = 12 + int(d_val * 1.3)
        duration = max(10, int(base * wx_mod))

        return idx, lane, duration

    def reward(self, bef, aft, action, mod):
        tb=sum(bef.values()); ta=sum(aft.values())
        gdirs,dur = self.ACTIONS[action]
        r = (tb-ta)*3.0 - ta*0.5 - (dur/25.0)*1.5
        if tb>0 and max(bef,key=bef.get) in gdirs: r += 3.0
        if mod>1.1 and dur<15: r -= 1.5
        return r

    def update(self, s, a, r, ns):
        for x in [s,ns]:
            if x not in self.q: self.q[x]=[0.0]*8
        td = r + self.gamma*max(self.q[ns])
        self.q[s][a] += self.alpha*(td-self.q[s][a])
        self.hist.append(round(r,2))
        self.total += r
        self.eps = max(self.eps_min, self.eps*self.eps_d)
        self.ep += 1

    def q_preview(self):
        rows=[]
        for s,vals in list(self.q.items())[:6]:
            a=int(np.argmax(vals))
            rows.append({"state":list(s),"best_action":a,"best_q":round(vals[a],2)})
        return rows

    def stats(self):
        h=list(self.hist)
        avg=round(sum(h)/len(h),2) if h else 0
        smooth=[]
        for i in range(0,len(h),max(1,len(h)//20)):
            chunk=h[max(0,i-4):i+1]
            smooth.append(round(sum(chunk)/len(chunk),2))
        return {"episode":self.ep,"epsilon":round(self.eps,4),
                "avg_reward":avg,"total":round(self.total,1),
                "q_states":len(self.q),"history":h[-40:],
                "smooth":smooth,"q_preview":self.q_preview()}

# ════════════════════════════════════════════════════════════════════════
#  ENERGY TRACKER
# ════════════════════════════════════════════════════════════════════════
class EnergyTracker:
    def __init__(self):
        self._mwh  = 0.0
        self._hist = deque(maxlen=150)
        self._lock = threading.Lock()
        self.running = False

    def run(self):
        self.running = True
        while self.running:
            time.sleep(2)
            mw = PI_MW + len(DIRECTIONS)*LED_MW
            with self._lock:
                self._mwh += mw*(2/3600)
                self._hist.append(round(mw/1000,3))

    def get(self):
        with self._lock:
            h=list(self._hist)
            return {"watts_now":h[-1] if h else 0,
                    "kwh_total":round(self._mwh/1e6,5),"history":h}

    def stop(self): self.running = False

# ════════════════════════════════════════════════════════════════════════
#  TRAFFIC CONTROLLER — fixed yellow transition
# ════════════════════════════════════════════════════════════════════════
class TrafficController:
    YELLOW_S = 3

    def __init__(self, ir, det, wx, agent, energy):
        self.ir      = ir
        self.det     = det
        self.wx      = wx
        self.agent   = agent
        self.energy  = energy
        self.signals = {d:"RED" for d in DIRECTIONS}
        self.green_dirs=[]
        self.remaining =0
        self.phase_dur =0
        self.amb       =False
        self.cleared   =0
        self.log       =deque(maxlen=50)
        self._lock     =threading.Lock()
        self.running   =False

    def _apply(self, gdirs, dur):
        # Step 1: turn everything OFF cleanly
        all_off()
        time.sleep(0.1)
        # Step 2: set each signal explicitly
        for d in DIRECTIONS:
            set_signal(d, "GREEN" if d in gdirs else "RED")
        with self._lock:
            self.signals    = {d:("GREEN" if d in gdirs else "RED") for d in DIRECTIONS}
            self.green_dirs = list(gdirs)
            self.phase_dur  = dur
            self.remaining  = dur

    def _yellow_transition(self, gdirs):
        """Explicit yellow: turn off green first, then set yellow, then all red."""
        # Turn off green pins first
        for d in gdirs:
            _led(LED_PINS[d]["G"], False)
        time.sleep(0.05)
        # Now set yellow on the green dirs only
        for d in gdirs:
            _led(LED_PINS[d]["Y"], True)
        with self._lock:
            for d in gdirs: self.signals[d] = "YELLOW"
        time.sleep(self.YELLOW_S)
        # Turn off yellow, set all red
        all_off()
        time.sleep(0.05)
        all_red()
        with self._lock:
            self.signals = {d:"RED" for d in DIRECTIONS}

    def _wait(self, dur):
        for t in range(dur):
            time.sleep(1)
            with self._lock: self.remaining = dur-t-1
            if not self.running: return False
            if self.det.is_ambulance()[0] and AMBULANCE_LANE not in self.green_dirs:
                return False
        return True

    def _log(self, gdirs, dur, density, amb=False):
        with self._lock:
            self.log.appendleft({
                "time":time.strftime("%H:%M:%S"),
                "green":list(gdirs),"duration":dur,
                "density":dict(density),"total":sum(density.values()),
                "amb":amb})

    def _amb_phase(self):
        print("[CTRL] AMBULANCE OVERRIDE")
        with self._lock: self.amb=True
        dens=self.ir.get_density()
        self._log([AMBULANCE_LANE],30,dens,amb=True)
        self._apply([AMBULANCE_LANE],30)
        for _ in range(60):
            time.sleep(1)
            if not self.det.is_ambulance()[0]: break
        self._yellow_transition([AMBULANCE_LANE])
        with self._lock: self.amb=False
        print("[CTRL] Ambulance cleared")

    def run(self):
        self.running   = True
        self._seq_idx  = 3   # start at 3 so first rotation goes to NORTH (idx 0)
        time.sleep(0.5)

        while self.running:
            # ── Ambulance override ─────────────────────────────────────
            if self.det.is_ambulance()[0]:
                self._amb_phase()
                continue

            # ── RL + sequential decision ───────────────────────────────
            d_bef   = self.ir.get_density()
            weather = self.wx.get()
            s       = self.agent.state(d_bef)
            a       = self.agent.choose(s)

            # Sequential with density override
            seq_idx, lane, dur = self.agent.choose_sequential(
                self._seq_idx, d_bef, weather["modifier"])
            self._seq_idx = seq_idx

            gdirs = [lane]
            # RL still learns in background using its own action
            dur_rl_base = self.agent.ACTIONS[a][1]
            # Final duration: use sequential calc (density-aware)
            dur = max(10, dur)

            self._log(gdirs, dur, d_bef)
            self._apply(gdirs, dur)
            self._wait(dur)
            self._yellow_transition(gdirs)

            d_aft = self.ir.get_density()
            ns    = self.agent.state(d_aft)
            r     = self.agent.reward(d_bef, d_aft, a, weather["modifier"])
            self.agent.update(s, a, r, ns)

            with self._lock:
                self.cleared += max(0, sum(d_bef.values())-sum(d_aft.values()))
        cleanup()

    def status(self):
        with self._lock:
            return {"signals":dict(self.signals),"green":list(self.green_dirs),
                    "remaining":self.remaining,"phase_dur":self.phase_dur,
                    "amb":self.amb,"cleared":self.cleared,"log":list(self.log)[:12]}

# ════════════════════════════════════════════════════════════════════════
#  DASHBOARD HTML
# ════════════════════════════════════════════════════════════════════════
DASH = r"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8"><title>AI Traffic — SRMIST</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg0:#05080f;--bg1:#080d18;--bg2:#0d1420;--bg3:#111b2a;--bg4:#162133;
  --bd:#192840;--bd2:#1f3250;
  --t1:#dce8ff;--t2:#7b92b2;--t3:#3d5470;
  --G:#00ff88;--Gbg:rgba(0,255,136,.07);--Gb:rgba(0,255,136,.3);
  --R:#ff2952;--Rbg:rgba(255,41,82,.07);--Rb:rgba(255,41,82,.3);
  --Y:#ffcc00;--Ybg:rgba(255,204,0,.07);--Yb:rgba(255,204,0,.3);
  --B:#3d9eff;--B2:#7ec8ff;
  --amb:#ff7a00;--ambbg:rgba(255,122,0,.1);
  --pu:#c471ed;--pu2:#f64f59;
  --mono:'JetBrains Mono',monospace;
  --sans:'Inter',sans-serif;
}
html,body{height:100%;background:var(--bg0);color:var(--t1);
  font-family:var(--sans);font-size:13px;overflow:hidden;margin:0}

.top{height:48px;display:flex;align-items:center;justify-content:space-between;
  padding:0 20px;background:var(--bg1);border-bottom:1px solid var(--bd);z-index:10;
  position:relative}
.top::after{content:'';position:absolute;bottom:0;left:0;right:0;height:1px;
  background:linear-gradient(90deg,transparent,var(--G),var(--B),transparent);opacity:.4}
.tl{display:flex;align-items:center;gap:12px}
.ldot{width:8px;height:8px;border-radius:50%;background:var(--G);
  animation:pr 1.8s infinite}
@keyframes pr{0%,100%{box-shadow:0 0 0 0 rgba(0,255,136,.5)}
  60%{box-shadow:0 0 0 7px transparent}}
.brand{font-size:15px;font-weight:600}.brand em{color:var(--B2);font-style:normal}
.sub{font-size:11px;color:var(--t3);font-family:var(--mono);margin-top:1px}
.chips{display:flex;gap:6px}
.chip{background:var(--bg3);border:1px solid var(--bd2);border-radius:6px;
  padding:4px 10px;font-size:11px;color:var(--t2);font-family:var(--mono)}
.chip b{color:var(--B2)}
.chip.amb-chip{border-color:rgba(255,122,0,.5);color:var(--amb);display:none}
.chip.amb-chip.on{display:block;animation:ab .6s infinite}
@keyframes ab{0%,100%{opacity:1}50%{opacity:.4}}

.layout{display:grid;grid-template-columns:270px 1fr 295px;height:calc(100vh - 48px);overflow:hidden}
.col{overflow-y:auto;overflow-x:hidden}
.col.L{background:var(--bg1);border-right:1px solid var(--bd);padding:10px}
.col.M{padding:10px;display:flex;flex-direction:column;gap:8px;overflow-y:auto;overflow-x:hidden}
.col.R{background:var(--bg1);border-left:1px solid var(--bd);padding:10px;overflow-y:scroll}

.card{background:var(--bg2);border:1px solid var(--bd);border-radius:10px;overflow:hidden;margin-bottom:9px}
.card:last-child{margin-bottom:0}
.ch{padding:8px 14px;border-bottom:1px solid var(--bd);background:var(--bg3);
  display:flex;align-items:center;justify-content:space-between}
.ch-t{font-size:10px;font-weight:500;text-transform:uppercase;letter-spacing:.1em;color:var(--t3)}
.ch-b{font-size:9px;font-family:var(--mono);padding:2px 7px;border-radius:3px;font-weight:500}
.cb{padding:12px 14px}

/* intersection */
.igrid{display:grid;grid-template-columns:repeat(3,78px);
  grid-template-rows:repeat(3,90px);gap:6px;justify-content:center;padding:14px 6px}
.sw{display:flex;justify-content:center;align-items:center}
.sig{width:74px;height:86px;border-radius:12px;display:flex;flex-direction:column;
  align-items:center;justify-content:center;gap:6px;
  border:1px solid var(--bd2);transition:all .35s;position:relative;overflow:hidden}
.sig::before{content:'';position:absolute;inset:0;opacity:0;transition:opacity .4s}
.lts{display:flex;flex-direction:column;gap:4px}
.b{width:14px;height:14px;border-radius:50%;opacity:.1;transition:all .35s}
.slbl{font-size:9px;font-weight:600;letter-spacing:.07em;font-family:var(--mono);z-index:1}

.sig.RED{background:var(--Rbg);border-color:var(--Rb)}
.sig.RED .b.r{background:var(--R);opacity:1;box-shadow:0 0 8px var(--R),0 0 20px rgba(255,41,82,.35)}
.sig.RED .slbl{color:var(--R)}

.sig.GREEN{background:var(--Gbg);border-color:var(--Gb)}
.sig.GREEN::before{background:radial-gradient(circle at 50% 30%,rgba(0,255,136,.14),transparent 70%);opacity:1}
.sig.GREEN .b.g{background:var(--G);opacity:1;box-shadow:0 0 10px var(--G),0 0 24px rgba(0,255,136,.45)}
.sig.GREEN .slbl{color:var(--G)}

.sig.YELLOW{background:var(--Ybg);border-color:var(--Yb)}
.sig.YELLOW .b.y{background:var(--Y);opacity:1;box-shadow:0 0 8px var(--Y),0 0 20px rgba(255,204,0,.4)}
.sig.YELLOW .slbl{color:var(--Y)}

.cx{width:78px;height:90px;display:flex;align-items:center;justify-content:center;
  background:var(--bg3);border-radius:8px;border:1px solid var(--bd);color:var(--t3);font-size:18px}

.tblock{text-align:center;padding:6px 0 14px}
.tnum{font-size:50px;font-weight:300;font-family:var(--mono);line-height:1;transition:color .3s}
.cG{color:var(--G)}.cR{color:var(--R)}.cY{color:var(--Y)}.cI{color:var(--t3)}
.tsub{font-size:10px;color:var(--t3);margin-top:3px;letter-spacing:.04em}
.ppills{display:flex;gap:5px;justify-content:center;flex-wrap:wrap;margin-top:10px}
.pill{padding:3px 10px;border-radius:5px;font-size:10px;font-family:var(--mono);font-weight:500;border:1px solid}
.pG{background:var(--Gbg);color:var(--G);border-color:var(--Gb)}
.pR{background:var(--Rbg);color:var(--R);border-color:var(--Rb)}
.pA{background:var(--ambbg);color:var(--amb);border-color:rgba(255,122,0,.4)}

/* lanes */
.lane{margin-bottom:12px}.lane:last-child{margin-bottom:4px}
.lhead{display:flex;justify-content:space-between;align-items:center;margin-bottom:5px}
.lname{font-size:11px;font-weight:500;font-family:var(--mono);color:var(--t2);display:flex;align-items:center;gap:5px}
.lsig{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.lval{font-size:13px;font-weight:700;color:var(--t1)}
.bt{height:12px;background:var(--bg3);border-radius:6px;border:1px solid var(--bd);overflow:hidden}
.bf{height:100%;border-radius:6px;transition:width .5s}
.bN{background:linear-gradient(90deg,#0077ff,#00c6ff)}
.bS{background:linear-gradient(90deg,#ff416c,#ff4b2b)}
.bE{background:linear-gradient(90deg,#f7971e,#ffd200)}
.bW{background:linear-gradient(90deg,#7f00ff,#e100ff)}
.dl{font-size:9px;color:var(--t3);margin-top:3px;display:flex;justify-content:space-between}
.dlb{font-family:var(--mono);padding:1px 5px;border-radius:3px;font-size:9px}
.dl-c{background:rgba(0,255,136,.1);color:var(--G)}
.dl-l{background:rgba(61,158,255,.1);color:var(--B2)}
.dl-m{background:rgba(255,204,0,.1);color:var(--Y)}
.dl-h{background:rgba(255,41,82,.15);color:var(--R)}

.mrow{display:grid;grid-template-columns:repeat(4,1fr);gap:7px}
.met{background:var(--bg2);border:1px solid var(--bd);border-radius:9px;padding:10px 8px;text-align:center}
.mv{font-size:22px;font-weight:300;font-family:var(--mono);line-height:1}
.mk{font-size:9px;color:var(--t3);margin-top:4px}

canvas{display:block;border-radius:6px;border:1px solid var(--bd);background:var(--bg3)}

.abanner{background:rgba(20,10,0,.97);border:2px solid var(--amb);
  border-radius:10px;padding:12px 18px;display:flex;align-items:center;gap:12px;
  position:fixed;top:60px;left:50%;transform:translateX(-50%);
  z-index:999;min-width:380px;box-shadow:0 0 30px rgba(255,122,0,.4);
  animation:ambPulse 1s infinite}
@keyframes ambPulse{0%,100%{box-shadow:0 0 20px rgba(255,122,0,.4)}
  50%{box-shadow:0 0 40px rgba(255,122,0,.8)}}
.abanner.h{display:none}
.atxt h3{font-size:14px;font-weight:600;color:var(--amb)}
.atxt p{font-size:11px;color:var(--t2);margin-top:2px}

/* weather */
.wx-top{display:flex;align-items:center;gap:12px;padding:8px 0 10px;border-bottom:1px solid var(--bd)}
.wx-ico{font-size:36px}
.wx-temps{flex:1}
.wx-temp{font-size:30px;font-weight:300;font-family:var(--mono)}
.wx-cond{font-size:11px;color:var(--t2);margin-top:1px}
.wx-loc{font-size:10px;color:var(--t3);margin-top:2px;display:flex;align-items:center;gap:3px}
.wx-mod-block{text-align:right}
.wx-mod-val{font-size:22px;font-weight:300;font-family:var(--mono);color:var(--Y)}
.wx-mod-lbl{font-size:9px;color:var(--t3);margin-top:2px}
.wxr{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid var(--bd)}
.wxr:last-child{border-bottom:none}
.wxk{font-size:11px;color:var(--t3)}.wxv{font-family:var(--mono);color:var(--B2);font-weight:500;font-size:12px}

/* rl */
.rl-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:10px}
.rl-box{background:var(--bg3);border:1px solid var(--bd);border-radius:7px;padding:8px 10px;text-align:center}
.rl-val{font-size:18px;font-weight:300;font-family:var(--mono);color:var(--pu)}
.rl-key{font-size:9px;color:var(--t3);margin-top:2px}
.clbl{font-size:9px;color:var(--t3);margin-bottom:4px;display:flex;justify-content:space-between}

.qt{width:100%;border-collapse:collapse;font-size:10px;font-family:var(--mono);margin-top:8px}
.qt th{padding:4px 6px;text-align:left;color:var(--t3);border-bottom:1px solid var(--bd);font-weight:500}
.qt td{padding:4px 6px;border-bottom:1px solid rgba(25,40,64,.8);color:var(--t2)}
.qt tr:last-child td{border-bottom:none}
.qt .qv{color:var(--pu)}.qt .qa{color:var(--B2)}

/* log */
.le{padding:7px 0;border-bottom:1px solid var(--bd)}
.le:last-child{border-bottom:none}
.lr1{display:flex;align-items:center;gap:5px;flex-wrap:wrap}
.lt{color:var(--t3);font-family:var(--mono);font-size:10px}
.lp{display:inline-flex;gap:3px;margin:0 3px}
.lpill{background:var(--Gbg);color:var(--G);border:1px solid var(--Gb);
  border-radius:4px;padding:1px 7px;font-size:10px;font-family:var(--mono)}
.lpill.a{background:var(--ambbg);color:var(--amb)}
.ldu{color:var(--B2);font-family:var(--mono);font-size:11px}
.lr2{display:flex;gap:6px;margin-top:4px;flex-wrap:wrap}
.ldseg{font-size:10px;font-family:var(--mono);padding:1px 5px;border-radius:3px;border:1px solid var(--bd)}
.lds0{color:var(--t3)}.lds1{color:var(--B2);background:rgba(61,158,255,.06)}
.lds2{color:var(--Y);background:rgba(255,204,0,.06)}.lds3{color:var(--R);background:rgba(255,41,82,.06)}

.arow{display:flex;gap:8px;align-items:center;padding:4px 0;border-bottom:1px solid var(--bd);font-size:11px}
.arow:last-child{border-bottom:none}
.aid{width:22px;font-family:var(--mono);font-weight:600;color:var(--B2)}
.adc{color:var(--t2);flex:1}.adu{font-family:var(--mono);color:var(--t3)}

.hrow{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid var(--bd);font-size:11px}
.hrow:last-child{border-bottom:none}
.hk{color:var(--t3)}.hv{color:var(--t1);font-family:var(--mono)}

.cw{position:relative;background:var(--bg3)}
.cw img{width:100%;display:block}
.cov{position:absolute;top:7px;left:7px;display:flex;gap:4px}
.cbg{background:rgba(0,0,0,.75);border:1px solid;border-radius:4px;
  padding:2px 7px;font-size:9px;font-family:var(--mono);font-weight:500}
.cbg.lv{border-color:var(--G);color:var(--G)}
.cbg.am{border-color:var(--amb);color:var(--amb);animation:ab .6s infinite}
.nc{height:90px;display:flex;align-items:center;justify-content:center;color:var(--t3);font-size:11px}

::-webkit-scrollbar{width:4px}::-webkit-scrollbar-thumb{background:var(--bd2);border-radius:2px}
</style></head><body>

<div class="top">
  <div class="tl">
    <div class="ldot"></div>
    <div>
      <div class="brand">AI Traffic <em>Management</em></div>
      <div class="sub">SRMIST ECE · RL+IR+CV · RPi3</div>
    </div>
  </div>
  <div class="chips">
    <div class="chip">Ep <b id="hep">0</b></div>
    <div class="chip">ε <b id="heps">0.35</b></div>
    <div class="chip" id="htm">--:--:--</div>
    <div class="chip" id="hwx">🌤 --°C</div>
    <div class="chip amb-chip" id="hamb">🚑 EMERGENCY</div>
  </div>
</div>

<div class="layout">

<!-- LEFT -->
<div class="col L">
  <div class="card">
    <div class="ch">
      <span class="ch-t">Intersection</span>
      <span class="ch-b" id="pbadge" style="background:rgba(255,41,82,.12);color:var(--R)">ALL RED</span>
    </div>
    <div class="igrid">
      <div></div>
      <div class="sw"><div class="sig RED" id="sN">
        <div class="lts"><div class="b r"></div><div class="b y"></div><div class="b g"></div></div>
        <div class="slbl">NORTH</div></div></div>
      <div></div>
      <div class="sw"><div class="sig RED" id="sW">
        <div class="lts"><div class="b r"></div><div class="b y"></div><div class="b g"></div></div>
        <div class="slbl">WEST</div></div></div>
      <div class="cx">✕</div>
      <div class="sw"><div class="sig RED" id="sE">
        <div class="lts"><div class="b r"></div><div class="b y"></div><div class="b g"></div></div>
        <div class="slbl">EAST</div></div></div>
      <div></div>
      <div class="sw"><div class="sig RED" id="sS">
        <div class="lts"><div class="b r"></div><div class="b y"></div><div class="b g"></div></div>
        <div class="slbl">SOUTH</div></div></div>
      <div></div>
    </div>
    <div class="tblock">
      <div class="tnum cI" id="tnum">—</div>
      <div class="tsub">SECONDS REMAINING</div>
      <div class="ppills" id="ppills"></div>
    </div>
  </div>

  <div class="card">
    <div class="ch"><span class="ch-t">Ambulance Monitor — NORTH</span></div>
    <div style="padding:7px">
      <div class="cw">
        <div class="nc" id="nc">⏳ Loading camera…</div>
        <img id="cimg" src="" style="display:none" alt="">
        <div class="cov">
          <span class="cbg lv">● LIVE</span>
          <span class="cbg am" id="ambadge" style="display:none">🚑</span>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- CENTER -->
<div class="col M">

  <div class="abanner h" id="abanner">
    <div style="font-size:24px">🚑</div>
    <div class="atxt">
      <h3>Emergency Vehicle Override</h3>
      <p>NORTH forced GREEN · All others RED · Clearing ambulance path</p>
    </div>
  </div>

  <div class="mrow" style="flex:0 0 auto">
    <div class="met"><div class="mv cG" id="mtot">0</div><div class="mk">TOTAL DENSITY</div></div>
    <div class="met"><div class="mv" style="color:var(--B2)" id="mclr">0</div><div class="mk">CLEARED</div></div>
    <div class="met"><div class="mv" style="color:var(--pu)" id="mqst">0</div><div class="mk">Q-STATES</div></div>
    <div class="met"><div class="mv" style="color:var(--Y)" id="mep">0</div><div class="mk">EPISODE</div></div>
  </div>

  <div class="card" style="flex:0 0 auto">
    <div class="ch">
      <span class="ch-t">Lane Density — IR Sensors</span>
      <span class="ch-b" style="background:rgba(61,158,255,.1);color:var(--B2)">LIVE</span>
    </div>
    <div style="padding:12px 16px 14px">
      {% for d in dirs %}
      <div style="margin-bottom:18px;flex-shrink:0">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
          <span style="font-size:12px;font-weight:500;font-family:var(--mono);color:var(--t2);display:flex;align-items:center;gap:6px">
            <span id="lsig{{ d }}" style="width:9px;height:9px;border-radius:50%;display:inline-block;flex-shrink:0"></span>
            {{ d }}
          </span>
          <span id="c{{ d }}" style="font-size:14px;font-weight:700;color:var(--t1)">0</span>
        </div>
        <div style="height:14px;background:var(--bg3);border-radius:7px;border:1px solid var(--bd);overflow:hidden">
          <div id="b{{ d }}" class="bf b{{ d[0] }}" style="width:0%;height:100%;border-radius:7px;transition:width .5s"></div>
        </div>
        <div style="display:flex;justify-content:space-between;margin-top:4px">
          <span id="dl{{ d }}" style="font-size:10px;color:var(--t3)">—</span>
          <span id="dlb{{ d }}" class="dlb dl-c" style="font-size:9px">CLEAR</span>
        </div>
      </div>
      {% endfor %}
    </div>
  </div>

  <div class="card" style="flex:0 0 auto">
    <div class="ch"><span class="ch-t">Real-time Power Consumption</span></div>
    <div class="cb">
      <div style="display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:8px">
        <div>
          <div style="font-size:28px;font-weight:300;font-family:var(--mono);color:var(--Y)" id="ew">0.0 W</div>
          <div style="font-size:9px;color:var(--t3)">current draw</div>
        </div>
        <div style="text-align:right">
          <div style="font-size:16px;font-family:var(--mono);color:var(--t2)" id="ek">0.00000 kWh</div>
          <div style="font-size:9px;color:var(--t3)">cumulative</div>
        </div>
      </div>
      <canvas id="ec" width="100%" height="60"></canvas>
    </div>
  </div>

  <div class="card" style="flex:0 0 auto">
    <div class="ch"><span class="ch-t">Phase Log</span></div>
    <div style="padding:8px 14px;max-height:260px;overflow-y:auto">
      <div id="plog"></div>
    </div>
  </div>

</div>

<!-- RIGHT -->
<div class="col R">

  <div class="card">
    <div class="ch"><span class="ch-t">Weather — Open-Meteo</span></div>
    <div class="cb">
      <div class="wx-top">
        <div class="wx-ico" id="wxico">🌤</div>
        <div class="wx-temps">
          <div class="wx-temp" id="wxtemp">--°C</div>
          <div class="wx-cond" id="wxcond">Loading…</div>
          <div class="wx-loc">📍 <span id="wxloc">Chennai, Tamil Nadu</span></div>
        </div>
        <div class="wx-mod-block">
          <div class="wx-mod-val" id="wxmod">1.0×</div>
          <div class="wx-mod-lbl">phase modifier</div>
        </div>
      </div>
      <div class="wxr"><span class="wxk">Wind speed</span><span class="wxv" id="wxwind">-- km/h</span></div>
      <div class="wxr"><span class="wxk">Duration impact</span><span class="wxv" id="wximpact" style="color:var(--G)">Normal</span></div>
    </div>
  </div>

  <div class="card">
    <div class="ch">
      <span class="ch-t">RL Agent — Q-Learning</span>
      <span class="ch-b" style="background:rgba(196,113,237,.1);color:var(--pu)">TRAINING</span>
    </div>
    <div class="cb">
      <div class="rl-grid">
        <div class="rl-box"><div class="rl-val" id="rep">0</div><div class="rl-key">EPISODE</div></div>
        <div class="rl-box"><div class="rl-val" style="color:var(--Y)" id="reps">0.35</div><div class="rl-key">EPSILON</div></div>
        <div class="rl-box"><div class="rl-val" style="color:var(--B2)" id="rqst">0</div><div class="rl-key">Q-STATES</div></div>
        <div class="rl-box"><div class="rl-val" style="color:var(--G)" id="rav">0.00</div><div class="rl-key">AVG REWARD</div></div>
      </div>
      <div class="clbl"><span>Reward per episode</span><span id="rtot" style="color:var(--pu)">Σ 0.0</span></div>
      <canvas id="rc" width="100%" height="55"></canvas>
      <div class="clbl" style="margin-top:8px"><span>Smoothed trend</span></div>
      <canvas id="rs" width="100%" height="38"></canvas>
      <div style="font-size:10px;color:var(--t3);margin:10px 0 4px;text-transform:uppercase;letter-spacing:.07em">Q-Table Preview</div>
      <table class="qt">
        <thead><tr><th>State (N·S·E·W)</th><th>Best Action</th><th>Q-val</th></tr></thead>
        <tbody id="qtb"></tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <div class="ch"><span class="ch-t">Action Space</span></div>
    <div class="cb" style="padding:8px 14px">
      <div class="arow"><span class="aid">A0</span><span class="adc">NORTH green</span><span class="adu">12s</span></div>
      <div class="arow"><span class="aid">A1</span><span class="adc">NORTH green</span><span class="adu">25s</span></div>
      <div class="arow"><span class="aid">A2</span><span class="adc">SOUTH green</span><span class="adu">12s</span></div>
      <div class="arow"><span class="aid">A3</span><span class="adc">SOUTH green</span><span class="adu">25s</span></div>
      <div class="arow"><span class="aid">A4</span><span class="adc">EAST green</span><span class="adu">12s</span></div>
      <div class="arow"><span class="aid">A5</span><span class="adc">EAST green</span><span class="adu">25s</span></div>
      <div class="arow"><span class="aid">A6</span><span class="adc">WEST green</span><span class="adu">12s</span></div>
      <div class="arow"><span class="aid">A7</span><span class="adc">WEST green</span><span class="adu">25s</span></div>
    </div>
  </div>

  <div class="card">
    <div class="ch"><span class="ch-t">Hardware — Pin Map</span></div>
    <div class="cb" style="padding:8px 14px">
      <div class="hrow"><span class="hk">NORTH R/Y/G</span><span class="hv">17 / 27 / 4</span></div>
      <div class="hrow"><span class="hk">SOUTH R/Y/G</span><span class="hv">5 / 6 / 13</span></div>
      <div class="hrow"><span class="hk">EAST  R/Y/G</span><span class="hv">10 / 26 / 7</span></div>
      <div class="hrow"><span class="hk">WEST  R/Y/G</span><span class="hv">11 / 16 / 12</span></div>
      <div class="hrow"><span class="hk">IR N/S/E/W</span><span class="hv">23/24/25/8</span></div>
      <div class="hrow"><span class="hk">GPIO</span>
        <span class="hv" style="color:{{ 'var(--G)' if gpio else 'var(--R)' }}">
          {{ 'Active' if gpio else 'Simulation' }}</span></div>
    </div>
  </div>

</div>
</div>

<script>
const $=id=>document.getElementById(id);
const D=["NORTH","SOUTH","EAST","WEST"];
const SI={"NORTH":"sN","SOUTH":"sS","EAST":"sE","WEST":"sW"};
const ACT={0:"N 12s",1:"N 25s",2:"S 12s",3:"S 25s",4:"E 12s",5:"E 25s",6:"W 12s",7:"W 25s"};

function chart(cv,data,sc,fc,zero){
  const W=cv.offsetWidth||cv.parentElement?.offsetWidth||200,H=cv.height;
  cv.width=W;
  const ctx=cv.getContext("2d");
  ctx.clearRect(0,0,W,H);
  if(data.length<2)return;
  const mn=Math.min(...data),mx=Math.max(...data);
  const pad=Math.max(Math.abs(mx-mn)*.1,0.5);
  const lo=mn-pad,hi=mx+pad,rng=hi-lo;
  const pts=data.map((v,i)=>({x:i/(data.length-1)*W,y:H-((v-lo)/rng*(H-4)+2)}));
  if(zero&&mn<0&&mx>0){
    const zy=H-((0-lo)/rng*(H-4)+2);
    ctx.beginPath();ctx.moveTo(0,zy);ctx.lineTo(W,zy);
    ctx.strokeStyle="rgba(255,255,255,.07)";ctx.lineWidth=1;ctx.stroke();
  }
  const g=ctx.createLinearGradient(0,0,0,H);
  g.addColorStop(0,fc);g.addColorStop(1,"transparent");
  ctx.beginPath();ctx.moveTo(pts[0].x,H);
  pts.forEach(p=>ctx.lineTo(p.x,p.y));
  ctx.lineTo(pts[pts.length-1].x,H);ctx.closePath();
  ctx.fillStyle=g;ctx.fill();
  ctx.beginPath();pts.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));
  ctx.strokeStyle=sc;ctx.lineWidth=1.8;ctx.lineJoin="round";ctx.stroke();
  const lp=pts[pts.length-1];
  ctx.beginPath();ctx.arc(lp.x,lp.y,3,0,Math.PI*2);
  ctx.fillStyle=sc;ctx.fill();
}

function wxIco(c){
  if(!c||c===0)return"☀️";if(c<=2)return"🌤";if(c===3)return"☁️";
  if(c<=48)return"🌫";if(c<=67)return"🌧";if(c<=77)return"❄️";
  if(c<=82)return"🌦";return"⛈";
}

function dlInfo(v){
  if(v===0)return["Clear","dl-c","CLEAR"];
  if(v<=2)return["Low","dl-l","LOW"];
  if(v<=6)return["Medium","dl-m","MED"];
  return["High — priority","dl-h","HIGH"];
}

// ── Ambulance Siren (Web Audio API) ─────────────────────────────────────
let _sirenInterval = null;
let _audioCtx = null;

function getAudioCtx(){
  if(!_audioCtx) _audioCtx = new (window.AudioContext||window.webkitAudioContext)();
  return _audioCtx;
}

function playSirenTone(freqStart, freqEnd, duration, startTime, ctx){
  const osc  = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.type = 'sawtooth';
  osc.frequency.setValueAtTime(freqStart, startTime);
  osc.frequency.linearRampToValueAtTime(freqEnd, startTime + duration);
  gain.gain.setValueAtTime(0.0, startTime);
  gain.gain.linearRampToValueAtTime(0.45, startTime + 0.05);
  gain.gain.setValueAtTime(0.45, startTime + duration - 0.05);
  gain.gain.linearRampToValueAtTime(0.0, startTime + duration);
  osc.start(startTime);
  osc.stop(startTime + duration);
}

function playAmbulanceSiren(){
  stopAmbulanceSiren();
  function cycle(){
    try{
      const ctx  = getAudioCtx();
      const now  = ctx.currentTime;
      // High-low wail: 1200Hz→800Hz then 800Hz→1200Hz
      playSirenTone(1200, 800, 0.55, now,       ctx);
      playSirenTone(800, 1200, 0.55, now + 0.55, ctx);
    }catch(e){}
  }
  cycle();
  _sirenInterval = setInterval(cycle, 1100);
}

function stopAmbulanceSiren(){
  if(_sirenInterval){ clearInterval(_sirenInterval); _sirenInterval=null; }
}

// Unlock AudioContext on first user interaction
document.addEventListener('click', ()=>{
  try{ getAudioCtx().resume(); }catch(e){}
}, {once:true});

window._ambWasOn = false;

async function poll(){
  try{
    const d=await fetch("/api/all").then(r=>r.json());
    $("htm").textContent=d.time;

    // signals
    D.forEach(dir=>{$(SI[dir]).className="sig "+d.signals[dir];});
    const vals=Object.values(d.signals);
    const tc=vals.includes("GREEN")?"G":vals.includes("YELLOW")?"Y":"R";
    const tn=$("tnum");
    tn.className="tnum c"+tc;
    tn.textContent=(vals.includes("GREEN")||vals.includes("YELLOW"))?d.remaining+"s":"—";

    // phase badge
    const pb=$("pbadge");
    if(d.ambulance){pb.textContent="🚑 EMERGENCY";pb.style.cssText="background:rgba(255,122,0,.15);color:var(--amb)";}
    else if(vals.includes("GREEN")){pb.textContent="● GREEN PHASE";pb.style.cssText="background:rgba(0,255,136,.12);color:var(--G)";}
    else if(vals.includes("YELLOW")){pb.textContent="● YELLOW";pb.style.cssText="background:rgba(255,204,0,.12);color:var(--Y)";}
    else{pb.textContent="● ALL RED";pb.style.cssText="background:rgba(255,41,82,.1);color:var(--R)";}

    // pills
    const pp=$("ppills");pp.innerHTML="";
    if(d.ambulance){pp.innerHTML='<span class="pill pA">🚑 EMERGENCY OVERRIDE</span>';}
    else{D.forEach(dir=>{pp.innerHTML+=`<span class="pill ${d.signals[dir]==="GREEN"?"pG":"pR"}">${dir}</span>`;});}

    // density
    let tot=0;
    D.forEach(dir=>{
      const v=d.density[dir]||0;tot+=v;
      $("c"+dir).textContent=v;
      $("b"+dir).style.width=(v*10)+"%";
      const [lbl,cls,badge]=dlInfo(v);
      $("dl"+dir).textContent=lbl;
      const db=$("dlb"+dir);db.textContent=badge;db.className="dlb "+cls;
      const sc=d.signals[dir]==="GREEN"?"var(--G)":d.signals[dir]==="YELLOW"?"var(--Y)":"var(--R)";
      $("lsig"+dir).style.cssText=`background:${sc};box-shadow:0 0 4px ${sc}`;
    });
    $("mtot").textContent=tot;$("mclr").textContent=d.cleared;$("mep").textContent=d.rl.episode;

    // camera
    if(d.frame_b64){
      $("cimg").src="data:image/jpeg;base64,"+d.frame_b64;
      $("cimg").style.display="block";$("nc").style.display="none";
    }
    $("ambadge").style.display=d.ambulance?"inline-block":"none";
    d.ambulance?$("abanner").classList.remove("h"):$("abanner").classList.add("h");
    d.ambulance?$("hamb").classList.add("on"):$("hamb").classList.remove("on");

    // Ambulance audio alert
    if(d.ambulance && !window._ambWasOn){
      window._ambWasOn = true;
      playAmbulanceSiren();
    } else if(!d.ambulance){
      window._ambWasOn = false;
      stopAmbulanceSiren();
    }

    // weather
    const wx=d.weather;
    $("wxico").textContent=wxIco(wx.wmo_code);
    $("wxtemp").textContent=wx.temperature+"°C";
    $("wxcond").textContent=wx.condition;
    $("wxloc").textContent=wx.location||"Chennai, Tamil Nadu";
    $("wxwind").textContent=wx.wind_speed+" km/h";
    $("wxmod").textContent=wx.modifier+"×";
    $("hwx").textContent=wxIco(wx.wmo_code)+" "+wx.temperature+"°C";
    const imp=wx.modifier>=1.4?"⚠ Heavy rain (+40%)":wx.modifier>=1.2?"+ Rain (+20%)":"✓ Normal";
    const ic=wx.modifier>=1.4?"var(--R)":wx.modifier>=1.2?"var(--Y)":"var(--G)";
    $("wximpact").textContent=imp;$("wximpact").style.color=ic;

    // RL
    const rl=d.rl;
    $("rep").textContent=rl.episode;$("hep").textContent=rl.episode;
    $("reps").textContent=rl.epsilon;$("heps").textContent=rl.epsilon;
    $("rqst").textContent=rl.q_states;$("mqst").textContent=rl.q_states;
    $("rav").textContent=rl.avg_reward;
    $("rtot").textContent="Σ "+rl.total;
    chart($("rc"),rl.history||[],"#c471ed","rgba(196,113,237,.15)",true);
    chart($("rs"),rl.smooth||[],"#f64f59","rgba(246,79,89,.12)",false);
    $("qtb").innerHTML=(rl.q_preview||[]).map(r=>{
      const s=r.state.map(v=>["L","M","H"][v]).join("·");
      return`<tr><td>${s}</td><td class="qa">A${r.best_action} ${ACT[r.best_action]}</td><td class="qv">${r.best_q}</td></tr>`;
    }).join("");

    // energy
    const en=d.energy;
    $("ew").textContent=en.watts_now.toFixed(2)+" W";
    $("ek").textContent=en.kwh_total.toFixed(5)+" kWh";
    chart($("ec"),en.history||[],"#ffcc00","rgba(255,204,0,.12)",false);

    // log
    $("plog").innerHTML=(d.log||[]).map(e=>{
      const pills=e.green.map(g=>`<span class="lpill${e.amb?' a':''}">${g}</span>`).join("");
      const segs=D.map(x=>{
        const v=e.density[x];const[,cls]=dlInfo(v);
        return`<span class="ldseg ${cls}">${x[0]}:${v}</span>`;
      }).join("");
      return`<div class="le">
        <div class="lr1"><span class="lt">${e.time}</span><span class="lp">${pills}</span><span class="ldu">${e.duration}s</span></div>
        <div class="lr2">${segs}</div></div>`;
    }).join("");

  }catch(e){console.warn(e);}
  setTimeout(poll,1500);
}
poll();
</script></body></html>"""

# ════════════════════════════════════════════════════════════════════════
#  FLASK
# ════════════════════════════════════════════════════════════════════════
app = Flask(__name__)
g_ir=g_det=g_wx=g_agent=g_ctrl=g_energy=None

@app.route("/")
def index():
    return render_template_string(DASH, dirs=DIRECTIONS, gpio=GPIO_OK)

@app.route("/api/all")
def api_all():
    st=g_ctrl.status()
    amb,conf=g_det.is_ambulance()
    return jsonify({
        "time":      time.strftime("%H:%M:%S"),
        "signals":   st["signals"],
        "green":     st["green"],
        "remaining": st["remaining"],
        "ambulance": amb,
        "density":   g_ir.get_density(),
        "weather":   g_wx.get(),
        "rl":        g_agent.stats(),
        "energy":    g_energy.get(),
        "cleared":   st["cleared"],
        "log":       st["log"],
        "frame_b64": g_det.get_b64(),
    })

# ════════════════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════════════════
def main():
    global g_ir,g_det,g_wx,g_agent,g_ctrl,g_energy
    print("="*52)
    print("  AI Traffic Management System — FINAL v2")
    print("  SRMIST ECE  |  Chennai, Tamil Nadu")
    print("  EAST → GPIO 10/9/7  |  NORTH-G → GPIO 4")
    print("="*52)

    g_ir     = IRManager()
    g_det    = AmbulanceDetector()
    g_wx     = WeatherService()
    g_agent  = RLAgent()
    g_energy = EnergyTracker()
    g_ctrl   = TrafficController(g_ir,g_det,g_wx,g_agent,g_energy)

    for name,fn in [("IR",g_ir.run),("CV",g_det.run),("WX",g_wx.run),
                    ("EN",g_energy.run),("CTRL",g_ctrl.run)]:
        threading.Thread(target=fn,daemon=True,name=name).start()
        print(f"[{name}] started")

    time.sleep(1)
    try:    ip=socket.gethostbyname(socket.gethostname())
    except: ip="0.0.0.0"
    print(f"[WEB] http://{ip}:5000\n")

    try:
        app.run(host="0.0.0.0",port=5000,debug=False,threaded=True)
    except KeyboardInterrupt:
        print("\n[STOP]")
        for x in [g_ir,g_det,g_wx,g_energy]: x.stop()
        g_ctrl.running=False
        cleanup()

if __name__=="__main__":
    main()
