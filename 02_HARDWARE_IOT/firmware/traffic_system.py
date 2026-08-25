#!/usr/bin/env python3
"""
AI Traffic Management System v5 — SRMIST ECE
Fix: gpio_init() called BEFORE any thread starts
"""

import time, threading, random, math, base64, socket
from collections import deque

import cv2
import numpy as np
from flask import Flask, render_template_string, jsonify

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

# ── Step 1: setmode ──────────────────────────────────────────────────────
try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO_OK = True
    print("[GPIO] BCM mode set")
except Exception as e:
    GPIO_OK = False
    print(f"[GPIO] Simulation ({e})")

# ── Pin definitions ──────────────────────────────────────────────────────
DIRECTIONS     = ["NORTH", "SOUTH", "EAST", "WEST"]
AMBULANCE_LANE = "NORTH"

LED_PINS = {
    "NORTH": {"R": 17, "Y": 27, "G": 22},
    "SOUTH": {"R":  5, "Y":  6, "G": 13},
    "EAST" : {"R": 19, "Y": 26, "G": 21},
    "WEST" : {"R": 20, "Y": 16, "G": 12},
}
IR_PINS = {"NORTH": 23, "SOUTH": 24, "EAST": 25, "WEST": 8}

LED_MW   = 35
PI_MW    = 2500

# ── Step 2: setup ALL pins immediately ──────────────────────────────────
def gpio_init():
    if not GPIO_OK:
        return
    for d, pins in LED_PINS.items():
        for c, p in pins.items():
            GPIO.setup(p, GPIO.OUT)
            GPIO.output(p, GPIO.LOW)
    for d, p in IR_PINS.items():
        GPIO.setup(p, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    print("[GPIO] All pins setup done")

# Call immediately — before ANY thread or class instantiation
gpio_init()

# ── GPIO helpers ─────────────────────────────────────────────────────────
def set_signal(direction, state):
    pins = LED_PINS[direction]
    if GPIO_OK:
        GPIO.output(pins["R"], GPIO.HIGH if state == "RED"    else GPIO.LOW)
        GPIO.output(pins["Y"], GPIO.HIGH if state == "YELLOW" else GPIO.LOW)
        GPIO.output(pins["G"], GPIO.HIGH if state == "GREEN"  else GPIO.LOW)

def all_red():
    for d in DIRECTIONS:
        set_signal(d, "RED")

def read_ir(direction):
    """LOW = vehicle present"""
    if not GPIO_OK:
        return False
    return GPIO.input(IR_PINS[direction]) == GPIO.LOW

def cleanup():
    if GPIO_OK:
        all_red()
        GPIO.cleanup()

# All red on startup
all_red()

# ════════════════════════════════════════════════════════════════════════
#  IR MANAGER
# ════════════════════════════════════════════════════════════════════════
class IRManager:
    WIN = 15

    def __init__(self):
        self._wins   = {d: deque([False]*self.WIN, maxlen=self.WIN) for d in DIRECTIONS}
        self._lock   = threading.Lock()
        self.running = False
        self._base   = {d: random.randint(2, 8) for d in DIRECTIONS}
        self._tick   = 0

    def _sim(self, d):
        b     = self._base[d]
        noise = math.sin(self._tick * 0.08 + DIRECTIONS.index(d) * 1.3) * 2.5
        prob  = max(0.05, min(0.95, (b + noise) / 10.0))
        return random.random() < prob

    def run(self):
        self.running = True
        while self.running:
            self._tick += 1
            if self._tick % 200 == 0:
                self._base = {d: random.randint(0, 9) for d in DIRECTIONS}
            for d in DIRECTIONS:
                val = read_ir(d) if GPIO_OK else self._sim(d)
                with self._lock:
                    self._wins[d].append(val)
            time.sleep(0.2)

    def get_density(self):
        with self._lock:
            return {d: int(sum(self._wins[d]) * 10 // self.WIN) for d in DIRECTIONS}

    def stop(self): self.running = False

# ════════════════════════════════════════════════════════════════════════
#  AMBULANCE DETECTOR
# ════════════════════════════════════════════════════════════════════════
class AmbulanceDetector:
    W_LO = np.array([0,   0, 190], dtype=np.uint8)
    W_HI = np.array([180, 50, 255], dtype=np.uint8)
    AREA = 1400

    def __init__(self):
        self._cap      = self._open()
        self._det      = False
        self._conf     = 0.0
        self._b64      = None
        self._lock     = threading.Lock()
        self.running   = False

    def _open(self):
        for bk, src in [(cv2.CAP_V4L2,"/dev/video0"),
                        (cv2.CAP_V4L2, 0),(cv2.CAP_ANY, 0)]:
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
        print("[CAM] Simulation")
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
                if not ret:
                    frame = np.zeros((240,320,3),dtype=np.uint8)
            else:
                frame = np.full((240,320,3),(25,28,35),dtype=np.uint8)
                sim   = (int(time.time())%120) < 8
                if sim:
                    cv2.rectangle(frame,(130,90),(190,150),(220,220,225),-1)

            det, conf, mask = self._detect(frame)
            vis = frame.copy()
            col = (0,255,100) if det else (80,80,150)
            cv2.rectangle(vis,(2,2),(318,238),col,2)
            cv2.rectangle(vis,(0,0),(320,18),(0,0,0),-1)
            cv2.putText(vis,f"{'AMBULANCE' if det else 'CLEAR'}  {conf*100:.0f}%",
                (4,13),cv2.FONT_HERSHEY_SIMPLEX,0.4,col,1)
            _, j = cv2.imencode(".jpg",vis,[cv2.IMWRITE_JPEG_QUALITY,72])
            b64  = base64.b64encode(j.tobytes()).decode()

            with self._lock:
                self._det  = det
                self._conf = conf
                self._b64  = b64
            time.sleep(0.15)

    def is_ambulance(self):
        with self._lock: return self._det, self._conf

    def get_b64(self):
        with self._lock: return self._b64

    def stop(self):
        self.running = False
        if self._cap: self._cap.release()

# ════════════════════════════════════════════════════════════════════════
#  WEATHER
# ════════════════════════════════════════════════════════════════════════
class WeatherService:
    URL = ("https://api.open-meteo.com/v1/forecast"
           "?latitude=12.8231&longitude=80.0444"
           "&current_weather=true&forecast_days=1")
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
        if not REQUESTS_OK: return
        try:
            cw   = requests.get(self.URL, timeout=8).json()["current_weather"]
            code = int(cw["weathercode"])
            mod  = 1.4 if code >= 65 else (1.2 if code >= 51 else 1.0)
            with self._lock:
                self.temperature = float(cw["temperature"])
                self.wind_speed  = float(cw["windspeed"])
                self.wmo_code    = code
                self.condition   = self.WMO.get(code,"Unknown")
                self.modifier    = mod
            print(f"[WX] {self.condition} {self.temperature}°C")
        except Exception as e:
            print(f"[WX] {e}")

    def run(self):
        self.running = True
        self._fetch()
        while self.running:
            time.sleep(600)
            self._fetch()

    def get(self):
        with self._lock:
            return {"temperature": round(self.temperature,1),
                    "condition":   self.condition,
                    "wmo_code":    self.wmo_code,
                    "wind_speed":  round(self.wind_speed,1),
                    "modifier":    round(self.modifier,2)}

    def stop(self): self.running = False

# ════════════════════════════════════════════════════════════════════════
#  RL AGENT
# ════════════════════════════════════════════════════════════════════════
class RLAgent:
    ACTIONS = {
        0:(["NORTH","SOUTH"],15), 1:(["NORTH","SOUTH"],30),
        2:(["EAST","WEST"],  15), 3:(["EAST","WEST"],  30),
        4:(["NORTH"],        15), 5:(["SOUTH"],        15),
        6:(["EAST"],         15), 7:(["WEST"],         15),
    }
    def __init__(self):
        self.q      = {}
        self.alpha  = 0.12
        self.gamma  = 0.90
        self.eps    = 0.35
        self.eps_min= 0.05
        self.eps_d  = 0.994
        self.ep     = 0
        self.total  = 0.0
        self.hist   = deque(maxlen=60)

    def _b(self,v): return 0 if v<=2 else (1 if v<=6 else 2)

    def state(self, density):
        return tuple(self._b(density[d]) for d in DIRECTIONS)

    def choose(self, s):
        if random.random() < self.eps or s not in self.q:
            return random.randint(0,7)
        return int(np.argmax(self.q[s]))

    def reward(self, bef, aft, action, mod):
        tb = sum(bef.values()); ta = sum(aft.values())
        gdirs, dur = self.ACTIONS[action]
        r  = (tb-ta)*3.0 - ta*0.5 - (dur/30.0)*1.5
        if tb>0 and max(bef,key=bef.get) in gdirs: r += 3.0
        if mod>1.1 and dur<20: r -= 1.5
        return r

    def update(self, s, a, r, ns):
        for x in [s,ns]:
            if x not in self.q: self.q[x]=[0.0]*8
        td = r + self.gamma*max(self.q[ns])
        self.q[s][a] += self.alpha*(td - self.q[s][a])
        self.hist.append(round(r,2))
        self.total += r
        self.eps = max(self.eps_min, self.eps*self.eps_d)
        self.ep  += 1

    def stats(self):
        h   = list(self.hist)
        avg = round(sum(h)/len(h),2) if h else 0
        return {"episode":self.ep,"epsilon":round(self.eps,4),
                "avg_reward":avg,"total":round(self.total,1),
                "q_states":len(self.q),"history":h[-30:]}

# ════════════════════════════════════════════════════════════════════════
#  ENERGY TRACKER
# ════════════════════════════════════════════════════════════════════════
class EnergyTracker:
    def __init__(self):
        self._mwh  = 0.0
        self._hist = deque(maxlen=120)
        self._lock = threading.Lock()
        self.running   = False
        self._get_sigs = None

    def attach(self, fn): self._get_sigs = fn

    def run(self):
        self.running = True
        while self.running:
            time.sleep(2)
            mw = PI_MW + (len(DIRECTIONS) * LED_MW)
            with self._lock:
                self._mwh += mw*(2/3600)
                self._hist.append(round(mw/1000,3))

    def get(self):
        with self._lock:
            h = list(self._hist)
            return {"watts_now":h[-1] if h else 0,
                    "kwh_total":round(self._mwh/1e6,5),
                    "history":h}

    def stop(self): self.running = False

# ════════════════════════════════════════════════════════════════════════
#  TRAFFIC CONTROLLER
# ════════════════════════════════════════════════════════════════════════
class TrafficController:
    YELLOW_S = 3

    def __init__(self, ir, det, wx, agent, energy):
        self.ir     = ir
        self.det    = det
        self.wx     = wx
        self.agent  = agent
        self.energy = energy

        self.signals   = {d:"RED" for d in DIRECTIONS}
        self.green_dirs= []
        self.remaining = 0
        self.phase_dur = 0
        self.amb       = False
        self.cleared   = 0
        self.log       = deque(maxlen=40)
        self._lock     = threading.Lock()
        self.running   = False

    def _apply(self, gdirs, dur):
        all_red()
        time.sleep(0.3)
        for d in DIRECTIONS:
            set_signal(d, "GREEN" if d in gdirs else "RED")
        with self._lock:
            self.signals    = {d:("GREEN" if d in gdirs else "RED") for d in DIRECTIONS}
            self.green_dirs = list(gdirs)
            self.phase_dur  = dur
            self.remaining  = dur

    def _wait(self, dur):
        """Count down, return False if interrupted by ambulance."""
        for t in range(dur):
            time.sleep(1)
            with self._lock: self.remaining = dur - t - 1
            if not self.running: return False
            amb, _ = self.det.is_ambulance()
            if amb and AMBULANCE_LANE not in self.green_dirs:
                return False
        return True

    def _yellow_red(self, gdirs):
        for d in gdirs: set_signal(d, "YELLOW")
        with self._lock:
            for d in gdirs: self.signals[d] = "YELLOW"
        time.sleep(self.YELLOW_S)
        all_red()
        with self._lock: self.signals = {d:"RED" for d in DIRECTIONS}

    def _log(self, gdirs, dur, density, amb=False):
        with self._lock:
            self.log.appendleft({
                "time":time.strftime("%H:%M:%S"),
                "green":list(gdirs),"duration":dur,
                "density":dict(density),"total":sum(density.values()),
                "amb":amb})

    def _amb_phase(self):
        print(f"[CTRL] AMBULANCE → {AMBULANCE_LANE}")
        with self._lock: self.amb = True
        dens = self.ir.get_density()
        self._log([AMBULANCE_LANE], 30, dens, amb=True)
        self._apply([AMBULANCE_LANE], 30)
        for _ in range(60):
            time.sleep(1)
            if not self.det.is_ambulance()[0]: break
        self._yellow_red([AMBULANCE_LANE])
        with self._lock: self.amb = False

    def run(self):
        self.running = True
        time.sleep(0.5)   # tiny settle after all threads start

        while self.running:
            # ambulance check
            if self.det.is_ambulance()[0]:
                self._amb_phase()
                continue

            # RL phase
            d_before = self.ir.get_density()
            weather  = self.wx.get()
            s        = self.agent.state(d_before)
            a        = self.agent.choose(s)
            gdirs, dur_base = self.agent.ACTIONS[a]
            dur      = max(10, int(dur_base * weather["modifier"]))

            self._log(gdirs, dur, d_before)
            self._apply(gdirs, dur)
            self._wait(dur)
            self._yellow_red(gdirs)

            d_after = self.ir.get_density()
            ns      = self.agent.state(d_after)
            r       = self.agent.reward(d_before, d_after, a, weather["modifier"])
            self.agent.update(s, a, r, ns)

            with self._lock:
                self.cleared += max(0, sum(d_before.values())-sum(d_after.values()))

        cleanup()

    def status(self):
        with self._lock:
            return {"signals":dict(self.signals),
                    "green":list(self.green_dirs),
                    "remaining":self.remaining,
                    "phase_dur":self.phase_dur,
                    "amb":self.amb,
                    "cleared":self.cleared,
                    "log":list(self.log)[:10]}

# ════════════════════════════════════════════════════════════════════════
#  DASHBOARD
# ════════════════════════════════════════════════════════════════════════
DASH = r"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>AI Traffic</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg0:#060810;--bg1:#0b0f1a;--bg2:#111827;--bg3:#1a2235;
  --bd:#1e2d45;--bd2:#253450;
  --t1:#e8f0fe;--t2:#94a3b8;--t3:#546a8a;
  --G:#00e676;--Gbg:rgba(0,230,118,.08);--Gb:rgba(0,230,118,.35);
  --R:#ff1744;--Rbg:rgba(255,23,68,.08);--Rb:rgba(255,23,68,.35);
  --Y:#ffd600;--Ybg:rgba(255,214,0,.08);--Yb:rgba(255,214,0,.35);
  --B2:#82b1ff;--amb:#ff6d00;--ambbg:rgba(255,109,0,.12);--pu:#e040fb;
  --mono:'JetBrains Mono',monospace;--sans:'Inter',sans-serif;
}
html,body{height:100%;background:var(--bg0);color:var(--t1);font-family:var(--sans);font-size:13px}
.topbar{display:flex;align-items:center;justify-content:space-between;
  padding:10px 20px;background:var(--bg1);border-bottom:1px solid var(--bd);
  position:sticky;top:0;z-index:99}
.tl{display:flex;align-items:center;gap:12px}
.dot{width:9px;height:9px;border-radius:50%;background:var(--G);
  animation:pr 2s infinite;box-shadow:0 0 0 0 rgba(0,230,118,.6)}
@keyframes pr{0%{box-shadow:0 0 0 0 rgba(0,230,118,.5)}
  70%{box-shadow:0 0 0 8px transparent}100%{box-shadow:0 0 0 0 transparent}}
.brand{font-size:15px;font-weight:600}.brand em{color:var(--B2);font-style:normal}
.sub{font-size:11px;color:var(--t3);font-family:var(--mono)}
.chips{display:flex;gap:7px}
.chip{background:var(--bg3);border:1px solid var(--bd2);border-radius:6px;
  padding:4px 10px;font-size:11px;color:var(--t2);font-family:var(--mono)}
.chip b{color:var(--B2)}

.layout{display:grid;grid-template-columns:260px 1fr 250px;height:calc(100vh - 47px)}
.col{overflow-y:auto;padding:10px}
.col.L{background:var(--bg1);border-right:1px solid var(--bd)}
.col.R{background:var(--bg1);border-left:1px solid var(--bd)}

.card{background:var(--bg2);border:1px solid var(--bd);border-radius:9px;
  overflow:hidden;margin-bottom:9px}
.card:last-child{margin-bottom:0}
.ch{padding:8px 13px;border-bottom:1px solid var(--bd);background:var(--bg3);
  font-size:10px;font-weight:500;text-transform:uppercase;letter-spacing:.08em;color:var(--t3)}
.cb{padding:11px 13px}

/* ── signals ── */
.igrid{display:grid;grid-template-columns:repeat(3,76px);
  grid-template-rows:repeat(3,86px);gap:5px;
  justify-content:center;align-items:center;padding:12px 6px}
.sw{display:flex;justify-content:center}
.sig{width:72px;height:82px;border-radius:10px;display:flex;flex-direction:column;
  align-items:center;justify-content:center;gap:5px;
  border:1px solid var(--bd2);transition:all .35s}
.lts{display:flex;flex-direction:column;gap:4px;align-items:center}
.b{width:13px;height:13px;border-radius:50%;opacity:.1;transition:all .35s}
.slbl{font-size:9px;font-weight:600;letter-spacing:.06em;font-family:var(--mono)}

.sig.RED   {background:var(--Rbg);border-color:var(--Rb)}
.sig.RED   .slbl{color:var(--R)}
.sig.RED   .b.r{background:var(--R);opacity:1;box-shadow:0 0 8px var(--R),0 0 16px rgba(255,23,68,.3)}
.sig.GREEN {background:var(--Gbg);border-color:var(--Gb);box-shadow:0 0 14px rgba(0,230,118,.12)}
.sig.GREEN .slbl{color:var(--G)}
.sig.GREEN .b.g{background:var(--G);opacity:1;box-shadow:0 0 8px var(--G),0 0 16px rgba(0,230,118,.3)}
.sig.YELLOW{background:var(--Ybg);border-color:var(--Yb)}
.sig.YELLOW .slbl{color:var(--Y)}
.sig.YELLOW .b.y{background:var(--Y);opacity:1;box-shadow:0 0 8px var(--Y)}

.cx{width:76px;height:86px;display:flex;align-items:center;justify-content:center;
  background:var(--bg3);border-radius:8px;border:1px solid var(--bd);color:var(--t3);font-size:15px}

.tblock{text-align:center;padding:5px 0 12px}
.tnum{font-size:44px;font-weight:300;font-family:var(--mono);line-height:1}
.G{color:var(--G)}.R{color:var(--R)}.Y{color:var(--Y)}.I{color:var(--t3)}
.tsub{font-size:10px;color:var(--t3);margin-top:3px}
.pills{display:flex;gap:4px;justify-content:center;flex-wrap:wrap;margin-top:8px}
.pill{padding:2px 9px;border-radius:4px;font-size:10px;
  font-family:var(--mono);font-weight:500;border:1px solid}
.pG{background:var(--Gbg);color:var(--G);border-color:var(--Gb)}
.pR{background:var(--Rbg);color:var(--R);border-color:var(--Rb)}
.pA{background:var(--ambbg);color:var(--amb);border-color:rgba(255,109,0,.4)}

/* ── lanes ── */
.lane{margin-bottom:10px}.lane:last-child{margin-bottom:0}
.lh{display:flex;justify-content:space-between;margin-bottom:4px}
.ln{font-size:11px;font-weight:500;font-family:var(--mono);color:var(--t2)}
.lv{font-size:12px;font-weight:700;color:var(--t1)}
.bt{height:10px;background:var(--bg3);border-radius:5px;border:1px solid var(--bd);overflow:hidden}
.bf{height:100%;border-radius:5px;transition:width .5s ease}
.bN{background:linear-gradient(90deg,#00b4d8,#0096c7)}
.bS{background:linear-gradient(90deg,#ff4d6d,#c9184a)}
.bE{background:linear-gradient(90deg,#ffd60a,#fca311)}
.bW{background:linear-gradient(90deg,#7b2d8b,#9d4edd)}
.dl{font-size:9px;color:var(--t3);margin-top:3px}

/* ── metrics ── */
.mrow{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-bottom:9px}
.met{background:var(--bg2);border:1px solid var(--bd);border-radius:8px;padding:9px;text-align:center}
.mv{font-size:22px;font-weight:300;font-family:var(--mono);color:var(--G)}
.mk{font-size:10px;color:var(--t3);margin-top:2px}

/* ── energy ── */
.ew{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px}
.ewv{font-size:24px;font-weight:300;font-family:var(--mono);color:var(--Y)}
.es{font-size:9px;color:var(--t3);margin-top:2px}
.ekv{font-size:15px;font-family:var(--mono);color:var(--t2)}
canvas{width:100%;display:block;background:var(--bg3);
  border-radius:5px;border:1px solid var(--bd)}

/* ── amb ── */
.abanner{background:var(--ambbg);border:1px solid rgba(255,109,0,.4);
  border-radius:8px;padding:9px 13px;display:flex;align-items:center;gap:10px;margin-bottom:9px}
.abanner.h{display:none}
.atxt h3{font-size:13px;font-weight:600;color:var(--amb)}
.atxt p{font-size:11px;color:var(--t2);margin-top:2px}

/* ── wx ── */
.wxi{font-size:30px;text-align:center;padding:4px 0}
.wxt{font-size:34px;font-weight:300;font-family:var(--mono);text-align:center;padding:5px 0 2px}
.wxc{text-align:center;font-size:11px;color:var(--t2);margin-bottom:9px}
.wxr{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid var(--bd)}
.wxr:last-child{border-bottom:none}
.wxk{font-size:11px;color:var(--t3)}.wxv{font-size:12px;font-family:var(--mono);color:var(--B2);font-weight:500}
.mbar{height:5px;background:var(--bg3);border-radius:3px;margin-top:4px}
.mf{height:100%;border-radius:3px;background:linear-gradient(90deg,var(--G),var(--Y),var(--R));transition:width .5s}

/* ── rl ── */
.rlr{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid var(--bd)}
.rlr:last-child{border-bottom:none}
.rlk{font-size:11px;color:var(--t3)}.rlv{font-size:12px;font-family:var(--mono);font-weight:500;color:var(--pu)}
.slbl{font-size:9px;color:var(--t3);margin:8px 0 3px}

/* ── log ── */
.le{padding:5px 0;border-bottom:1px solid var(--bd);font-size:11px}
.le:last-child{border-bottom:none}
.lt{color:var(--t3);font-family:var(--mono);font-size:10px}
.lp{display:inline-flex;gap:3px;margin:0 4px}
.lpill{background:var(--Gbg);color:var(--G);border:1px solid var(--Gb);
  border-radius:3px;padding:0 5px;font-size:10px;font-family:var(--mono)}
.lpill.a{background:var(--ambbg);color:var(--amb)}
.ldu{color:var(--B2);font-family:var(--mono)}
.ld2{color:var(--t3);font-size:10px;margin-top:2px;font-family:var(--mono)}

/* ── action ── */
.ar{display:flex;gap:6px;padding:4px 0;border-bottom:1px solid var(--bd);font-size:11px;align-items:center}
.ar:last-child{border-bottom:none}
.aid{width:22px;font-family:var(--mono);font-weight:600;color:var(--B2)}
.adc{color:var(--t2);flex:1}.adu{font-family:var(--mono);color:var(--t3)}

/* ── hw ── */
.hwr{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid var(--bd);font-size:11px}
.hwr:last-child{border-bottom:none}
.hwk{color:var(--t3)}.hwv{color:var(--t1)}

/* ── cam ── */
.cw{position:relative;background:var(--bg3)}
.cw img{width:100%;display:block}
.cov{position:absolute;top:7px;left:7px;display:flex;gap:4px}
.cbg{background:rgba(0,0,0,.72);border:1px solid;border-radius:4px;
  padding:2px 6px;font-size:9px;font-family:var(--mono);font-weight:500}
.cbg.lv{border-color:var(--G);color:var(--G)}
.cbg.am{border-color:var(--amb);color:var(--amb);animation:ab .7s infinite}
@keyframes ab{0%,100%{opacity:1}50%{opacity:.3}}
.nc{height:90px;display:flex;flex-direction:column;align-items:center;
  justify-content:center;color:var(--t3);gap:4px;font-size:11px}

::-webkit-scrollbar{width:4px}::-webkit-scrollbar-thumb{background:var(--bd2);border-radius:2px}
</style></head><body>

<div class="topbar">
  <div class="tl">
    <div class="dot"></div>
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
  </div>
</div>

<div class="layout">
<!-- LEFT -->
<div class="col L">
  <div class="card">
    <div class="ch">Intersection</div>
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
      <div class="tnum I" id="tnum">—</div>
      <div class="tsub">seconds remaining</div>
      <div class="pills" id="ppills"></div>
    </div>
  </div>
  <div class="card">
    <div class="ch">Ambulance Monitor — NORTH</div>
    <div style="padding:7px">
      <div class="cw" id="cw">
        <div class="nc" id="nc">⏳ Loading…</div>
        <img id="cimg" src="" style="display:none" alt="">
        <div class="cov">
          <span class="cbg lv">● LIVE</span>
          <span class="cbg am" id="amb" style="display:none">🚑 AMB</span>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- CENTER -->
<div class="col">
  <div class="abanner h" id="ab">
    <div style="font-size:22px">🚑</div>
    <div class="atxt"><h3>Emergency Override</h3>
      <p>NORTH lane forced GREEN — clearing ambulance</p></div>
  </div>
  <div class="mrow">
    <div class="met"><div class="mv" id="mtot">0</div><div class="mk">Total density</div></div>
    <div class="met"><div class="mv" id="mclr">0</div><div class="mk">Vehicles cleared</div></div>
    <div class="met"><div class="mv" id="mqst">0</div><div class="mk">Q-states</div></div>
  </div>
  <div class="card">
    <div class="ch">Lane Density — IR Sensors</div>
    <div class="cb">
      {% for d in dirs %}
      <div class="lane">
        <div class="lh"><span class="ln">{{ d }}</span><span class="lv" id="c{{ d }}">0</span></div>
        <div class="bt"><div class="bf b{{ d[0] }}" id="b{{ d }}" style="width:0%"></div></div>
        <div class="dl" id="dl{{ d }}">—</div>
      </div>
      {% endfor %}
    </div>
  </div>
  <div class="card">
    <div class="ch">Real-time Power Consumption</div>
    <div class="cb">
      <div class="ew">
        <div><div class="ewv" id="ew">0.0 W</div><div class="es">current draw</div></div>
        <div style="text-align:right"><div class="ekv" id="ek">0.00000 kWh</div>
          <div class="es">total consumed</div></div>
      </div>
      <canvas id="ec" height="60"></canvas>
    </div>
  </div>
  <div class="card">
    <div class="ch">Phase Log</div>
    <div class="cb" style="padding:7px 13px"><div id="pl"></div></div>
  </div>
</div>

<!-- RIGHT -->
<div class="col R">
  <div class="card">
    <div class="ch">Weather — Open-Meteo</div>
    <div class="cb">
      <div class="wxi" id="wxi">🌤</div>
      <div class="wxt" id="wxt">--°C</div>
      <div class="wxc" id="wxc">Loading…</div>
      <div class="wxr"><span class="wxk">Wind</span><span class="wxv" id="wxw">-- km/h</span></div>
      <div class="wxr"><span class="wxk">Modifier</span><span class="wxv" id="wxm">1.0×</span></div>
      <div style="font-size:9px;color:var(--t3);margin-top:5px">Signal duration impact</div>
      <div class="mbar"><div class="mf" id="mf" style="width:0%"></div></div>
    </div>
  </div>
  <div class="card">
    <div class="ch">RL Agent — Q-Learning</div>
    <div class="cb">
      <div class="rlr"><span class="rlk">Algorithm</span><span class="rlv">Q-Learning</span></div>
      <div class="rlr"><span class="rlk">Episode</span><span class="rlv" id="rep">0</span></div>
      <div class="rlr"><span class="rlk">Avg reward</span><span class="rlv" id="rav">0.00</span></div>
      <div class="rlr"><span class="rlk">Total reward</span><span class="rlv" id="rtot">0.0</span></div>
      <div class="rlr"><span class="rlk">Epsilon ε</span><span class="rlv" id="reps">0.35</span></div>
      <div class="rlr"><span class="rlk">Q-states</span><span class="rlv" id="rqst">0</span></div>
      <div class="slbl">Reward history</div>
      <canvas id="rc" height="44"></canvas>
    </div>
  </div>
  <div class="card">
    <div class="ch">Action Space</div>
    <div class="cb" style="padding:7px 13px">
      <div class="ar"><span class="aid">A0</span><span class="adc">N+S green</span><span class="adu">15s</span></div>
      <div class="ar"><span class="aid">A1</span><span class="adc">N+S green</span><span class="adu">30s</span></div>
      <div class="ar"><span class="aid">A2</span><span class="adc">E+W green</span><span class="adu">15s</span></div>
      <div class="ar"><span class="aid">A3</span><span class="adc">E+W green</span><span class="adu">30s</span></div>
      <div class="ar"><span class="aid">A4</span><span class="adc">N only</span><span class="adu">15s</span></div>
      <div class="ar"><span class="aid">A5</span><span class="adc">S only</span><span class="adu">15s</span></div>
      <div class="ar"><span class="aid">A6</span><span class="adc">E only</span><span class="adu">15s</span></div>
      <div class="ar"><span class="aid">A7</span><span class="adc">W only</span><span class="adu">15s</span></div>
    </div>
  </div>
  <div class="card">
    <div class="ch">Hardware</div>
    <div class="cb" style="padding:7px 13px">
      <div class="hwr"><span class="hwk">MCU</span><span class="hwv">Raspberry Pi 3</span></div>
      <div class="hwr"><span class="hwk">GPIO</span>
        <span class="hwv" style="color:{{ 'var(--G)' if gpio else 'var(--R)' }}">
          {{ 'Active' if gpio else 'Simulation' }}</span></div>
      <div class="hwr"><span class="hwk">IR Sensors</span><span class="hwv">4× FC-51</span></div>
      <div class="hwr"><span class="hwk">LED Modules</span><span class="hwv">4× Traffic</span></div>
      <div class="hwr"><span class="hwk">Camera</span><span class="hwv">USB — NORTH</span></div>
    </div>
  </div>
</div>
</div>

<script>
const $=id=>document.getElementById(id);
const D=["NORTH","SOUTH","EAST","WEST"];
const SI={"NORTH":"sN","SOUTH":"sS","EAST":"sE","WEST":"sW"};

function drawLine(cv,data,sc,fc){
  const W=cv.offsetWidth,H=cv.offsetHeight;
  cv.width=W;cv.height=H;
  const ctx=cv.getContext("2d");
  ctx.clearRect(0,0,W,H);
  if(data.length<2)return;
  const mn=Math.min(...data)*.95,mx=Math.max(...data)*1.05,rng=mx-mn||1;
  const pts=data.map((v,i)=>({x:i/(data.length-1)*W,y:H-((v-mn)/rng*(H-8)+4)}));
  const g=ctx.createLinearGradient(0,0,0,H);
  g.addColorStop(0,fc);g.addColorStop(1,"transparent");
  ctx.beginPath();ctx.moveTo(pts[0].x,H);
  pts.forEach(p=>ctx.lineTo(p.x,p.y));
  ctx.lineTo(pts[pts.length-1].x,H);ctx.closePath();
  ctx.fillStyle=g;ctx.fill();
  ctx.beginPath();pts.forEach((p,i)=>i===0?ctx.moveTo(p.x,p.y):ctx.lineTo(p.x,p.y));
  ctx.strokeStyle=sc;ctx.lineWidth=1.6;ctx.lineJoin="round";ctx.stroke();
}

function wxIcon(c){
  if(c===0)return"☀️";if(c<=2)return"🌤";if(c===3)return"☁️";
  if(c<=48)return"🌫";if(c<=67)return"🌧";if(c<=77)return"❄️";
  if(c<=82)return"🌦";return"⛈";
}
function dlbl(v){
  if(v===0)return"Clear";if(v<=2)return"Low";
  if(v<=6)return"Medium";return"🔴 High — priority";
}

async function poll(){
  try{
    const d=await fetch("/api/all").then(r=>r.json());
    $("htm").textContent=d.time;

    // signals
    D.forEach(dir=>{$(SI[dir]).className="sig "+d.signals[dir];});
    const vals=Object.values(d.signals);
    const tc=vals.includes("GREEN")?"G":vals.includes("YELLOW")?"Y":"R";
    const tn=$("tnum");
    tn.className="tnum "+tc;
    tn.textContent=(vals.includes("GREEN")||vals.includes("YELLOW"))?d.remaining+"s":"—";
    const pp=$("ppills");pp.innerHTML="";
    if(d.ambulance){
      pp.innerHTML='<span class="pill pA">🚑 EMERGENCY</span>';
    } else {
      D.forEach(dir=>{
        pp.innerHTML+=`<span class="pill ${d.signals[dir]==="GREEN"?"pG":"pR"}">${dir}</span>`;
      });
    }

    // density
    let tot=0;
    D.forEach(dir=>{
      const v=d.density[dir]||0;tot+=v;
      $("c"+dir).textContent=v;
      $("b"+dir).style.width=(v*10)+"%";
      $("dl"+dir).textContent=dlbl(v);
    });
    $("mtot").textContent=tot;
    $("mclr").textContent=d.cleared;

    // camera
    if(d.frame_b64){
      $("cimg").src="data:image/jpeg;base64,"+d.frame_b64;
      $("cimg").style.display="block";$("nc").style.display="none";
    }
    $("amb").style.display=d.ambulance?"inline-block":"none";
    d.ambulance?$("ab").classList.remove("h"):$("ab").classList.add("h");

    // weather
    const wx=d.weather;
    $("wxi").textContent=wxIcon(wx.wmo_code||0);
    $("wxt").textContent=wx.temperature+"°C";
    $("wxc").textContent=wx.condition;
    $("wxw").textContent=wx.wind_speed+" km/h";
    $("wxm").textContent=wx.modifier+"×";
    $("mf").style.width=Math.min(100,(wx.modifier-1)*200)+"%";
    $("hwx").textContent=wxIcon(wx.wmo_code||0)+" "+wx.temperature+"°C";

    // RL
    const rl=d.rl;
    $("rep").textContent=rl.episode;$("hep").textContent=rl.episode;
    $("rav").textContent=rl.avg_reward;
    $("rtot").textContent=rl.total;
    $("reps").textContent=rl.epsilon;$("heps").textContent=rl.epsilon;
    $("rqst").textContent=rl.q_states;$("mqst").textContent=rl.q_states;
    drawLine($("rc"),rl.history||[],"#e040fb","rgba(160,0,255,.2)");

    // energy
    const en=d.energy;
    $("ew").textContent=en.watts_now.toFixed(2)+" W";
    $("ek").textContent=en.kwh_total.toFixed(5)+" kWh";
    drawLine($("ec"),en.history||[],"#ffd600","rgba(255,214,0,.2)");

    // log
    $("pl").innerHTML=(d.log||[]).map(e=>{
      const pills=e.green.map(g=>`<span class="lpill${e.amb?' a':''}">${g}</span>`).join("");
      const dc=D.map(x=>`${x[0]}:${e.density[x]}`).join(" ");
      return`<div class="le"><span class="lt">${e.time}</span>
        <span class="lp">${pills}</span><span class="ldu">${e.duration}s</span>
        <div class="ld2">${dc} · total:${e.total}</div></div>`;
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
    st = g_ctrl.status()
    amb, conf = g_det.is_ambulance()
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
    print("  AI Traffic Management System v5")
    print("  SRMIST ECE")
    print("="*52)

    # GPIO already init'd at module level — safe to create objects now
    g_ir     = IRManager()
    g_det    = AmbulanceDetector()
    g_wx     = WeatherService()
    g_agent  = RLAgent()
    g_energy = EnergyTracker()
    g_ctrl   = TrafficController(g_ir, g_det, g_wx, g_agent, g_energy)

    for name, fn in [("IR",g_ir.run),("CV",g_det.run),("WX",g_wx.run),
                     ("EN",g_energy.run),("CTRL",g_ctrl.run)]:
        threading.Thread(target=fn, daemon=True, name=name).start()
        print(f"[{name}] started")

    time.sleep(1)
    try:    ip = socket.gethostbyname(socket.gethostname())
    except: ip = "0.0.0.0"
    print(f"[WEB] http://{ip}:5000\n")

    try:
        app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\n[STOP]")
        for x in [g_ir,g_det,g_wx,g_energy]: x.stop()
        g_ctrl.running = False
        cleanup()

if __name__=="__main__":
    main()
