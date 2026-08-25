"""
TrafficLogicManager — RL-driven signal controller
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Replaces the old density-formula approach with a DQN agent.
The agent observes full state (density, wait, ambulance, pedestrian,
weather, current phase) and decides which lane gets green next.
"""

import threading
import time
import sqlite3
import random
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from rl_agent.dqn_agent import DQNAgent

MIN_GREEN = 5
MAX_GREEN = 45
WEATHER_EXTENSION = {0: 0, 0.5: 5, 1.0: 10}   # extra seconds in bad weather


class TrafficLogicManager:

    def __init__(self):
        self._lock    = threading.Lock()
        self._signals = {i: 'red' for i in range(1, 5)}
        self._wait    = {i: 0.0   for i in range(1, 5)}
        self._density = {i: 0     for i in range(1, 5)}
        self._ambulance  = {i: False for i in range(1, 5)}
        self._pedestrian = {i: False for i in range(1, 5)}
        self._counts  = {i: {'cars':0,'buses':0,'trucks':0,'motorcycles':0,'ambulances':0,'pedestrians':0} for i in range(1, 5)}
        self._weather_factor = 0.0     # 0=clear, 0.5=rain, 1.0=fog
        self._weather_label  = 'Clear'
        self._current_phase  = 0       # 0-3
        self._green_time     = {i: 0.0 for i in range(1, 5)}
        self._decision_mode  = 'initializing'
        self._prev_total_wait = 0.0
        self._cycle_count     = 0

        self.agent   = DQNAgent(model_path='models/dqn_traffic.weights.h5')
        self._running = True
        self._thread  = threading.Thread(target=self._cycle, daemon=True)
        self._thread.start()

        # Weather simulation thread
        self._wx_thread = threading.Thread(target=self._simulate_weather, daemon=True)
        self._wx_thread.start()

    def reset(self):
        with self._lock:
            for i in range(1, 5):
                self._signals[i]    = 'red'
                self._density[i]    = 0
                self._ambulance[i]  = False
                self._pedestrian[i] = False
                self._wait[i]       = 0.0
                self._green_time[i] = 0.0

    def update_lane(self, lane_id, density, amb, ped, cars, buses, trucks, motorcycles, ambulances, pedestrians):
        with self._lock:
            self._density[lane_id]    = density
            self._ambulance[lane_id]  = amb
            self._pedestrian[lane_id] = ped
            self._counts[lane_id]     = {
                'cars': cars, 'buses': buses, 'trucks': trucks,
                'motorcycles': motorcycles, 'ambulances': ambulances,
                'pedestrians': pedestrians
            }
            if self._signals[lane_id] == 'red':
                self._wait[lane_id] += 0.5   # accrue wait while red

    def get_signal(self, lane_id):
        with self._lock:
            return self._signals.get(lane_id, 'red')

    def get_green_time(self, lane_id):
        with self._lock:
            return self._green_time.get(lane_id, 0.0)

    def get_all_stats(self):
        with self._lock:
            stats = {}
            for i in range(1, 5):
                stats[str(i)] = {
                    'signal':     self._signals[i],
                    'density':    self._density[i],
                    'ambulance':  self._ambulance[i],
                    'pedestrian': self._pedestrian[i],
                    'green_time': round(self._green_time[i], 1),
                    'wait_time':  round(self._wait[i], 1),
                    **self._counts[i]
                }
            stats['weather']       = {'factor': self._weather_factor, 'label': self._weather_label}
            stats['decision_mode'] = self._decision_mode
            stats['rl']            = self.agent.get_status()
            stats['cycle']         = self._cycle_count
            return stats

    # ── State builder ──────────────────────────────────────────────────
    def _build_state(self):
        max_d = max(max(self._density.values(), default=1), 1)
        max_w = max(max(self._wait.values(),    default=1), 1)
        state = []
        state += [self._density[i] / max_d for i in range(1, 5)]
        state += [self._wait[i]    / max_w for i in range(1, 5)]
        state += [1.0 if self._ambulance[i]  else 0.0 for i in range(1, 5)]
        state += [1.0 if self._pedestrian[i] else 0.0 for i in range(1, 5)]
        state.append(self._weather_factor)
        state.append(self._current_phase / 3.0)
        return state

    def _calc_green_time(self, lane_id):
        d  = self._density[lane_id]
        wx = self._weather_factor
        # RL-informed base: more density → longer green (bounded)
        base = max(MIN_GREEN, min(MAX_GREEN - 5, d * 1.0))
        # weather extension
        ext  = 10 * wx
        # ambulance gets max
        if self._ambulance[lane_id]:
            return 15
        return round(min(MAX_GREEN, base + ext), 1)

    # ── Main cycle ─────────────────────────────────────────────────────
    def _cycle(self):
        while self._running:
            with self._lock:
                state     = self._build_state()
                prev_wait = self._prev_total_wait

            action, mode = self.agent.act(state)
            lane = action + 1   # 0-based → 1-based lane

            with self._lock:
                self._decision_mode = mode
                gt = self._calc_green_time(lane)

            # give green — pass mode so it gets logged to DB
            self._give_green(lane, gt, mode)

            # RL step
            with self._lock:
                next_state     = self._build_state()
                total_wait_now = sum(self._wait.values())

            reward = self.agent.compute_reward(state, action, prev_wait)
            self.agent.remember(state, action, reward, next_state, False)
            self.agent.replay()

            with self._lock:
                self._prev_total_wait = total_wait_now
                self._current_phase   = action
                self._cycle_count    += 1

    def _give_green(self, lane, duration, decision_mode):
        # set green for chosen lane, red for others
        with self._lock:
            for i in range(1, 5):
                self._signals[i] = 'green' if i == lane else 'red'
            self._green_time[lane] = duration

        elapsed = 0.0
        step    = 0.5
        while elapsed < duration and self._running:
            time.sleep(step)
            elapsed += step
            with self._lock:
                self._green_time[lane] = max(0, duration - elapsed)
                self._wait[lane] = 0.0    # reset wait for active lane

        # log to DB with decision mode
        with self._lock:
            counts = self._counts[lane].copy()
            gt_used = round(elapsed, 1)
        self._log(lane, counts, gt_used, decision_mode)

        # yellow phase for the active lane
        with self._lock:
            self._signals[lane]    = 'yellow'
            self._green_time[lane] = 0.0
        time.sleep(2)

        # all-red clearance phase
        with self._lock:
            self._signals[lane]    = 'red'
        time.sleep(1)

    def _log(self, lane, counts, green_time, decision_mode):
        try:
            db = sqlite3.connect('users.db')
            db.execute(
                '''INSERT INTO traffic_log
                   (lane, cars, buses, trucks, motorcycles, ambulances, pedestrians, total, green_time, decision_mode)
                   VALUES (?,?,?,?,?,?,?,?,?,?)''',
                (lane, counts['cars'], counts['buses'], counts['trucks'],
                 counts['motorcycles'], counts['ambulances'], counts['pedestrians'],
                 counts['cars']+counts['buses']+counts['trucks']+counts['motorcycles'],
                 green_time, decision_mode))
            db.commit()
            db.close()
        except Exception:
            pass

    # ── Weather simulation ─────────────────────────────────────────────
    def _simulate_weather(self):
        conditions = [
            (0.0,  'Clear ☀️'),
            (0.0,  'Clear ☀️'),
            (0.5,  'Rain 🌧️'),
            (0.5,  'Rain 🌧️'),
            (1.0,  'Fog 🌫️'),
            (0.25, 'Cloudy ⛅'),
        ]
        while self._running:
            factor, label = random.choice(conditions)
            with self._lock:
                self._weather_factor = factor
                self._weather_label  = label
            time.sleep(random.randint(30, 90))
