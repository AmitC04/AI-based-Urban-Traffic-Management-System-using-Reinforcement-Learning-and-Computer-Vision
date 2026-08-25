"""
VideoDetector — YOLOv8 + pedestrian + ambulance detection
Simulation fallback when no YOLO/video available.
"""

import cv2, threading, time, random
import numpy as np

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

# COCO class IDs
CLS_CAR   = 2
CLS_MOTO  = 3
CLS_BUS   = 5
CLS_TRUCK = 7
CLS_PERSON = 0   # pedestrian

VEHICLE_CLS = {2:'Car', 3:'Motorcycle', 5:'Bus', 7:'Truck'}
COLORS = {
    'Car':        (0, 165, 255),
    'Motorcycle': (0, 200, 100),
    'Bus':        (200, 100, 0),
    'Truck':      (100, 0, 200),
    'Person':     (0, 220, 220),
    'AMBULANCE':  (0, 0, 255),
}


class VideoDetector:
    def __init__(self, lane_id, video_path, logic_manager):
        self.lane_id       = lane_id
        self.video_path    = video_path
        self.logic_manager = logic_manager
        self._frame        = None
        self._lock         = threading.Lock()
        self._running      = False
        self._thread       = None

        # Live stats
        self.cars = self.buses = self.trucks = 0
        self.motorcycles = self.ambulances = self.pedestrians = 0
        self.density = 0
        self.ambulance_detected  = False
        self.pedestrian_detected = False

        # Load models
        self.vehicle_model   = None
        self.ambulance_model = None
        if YOLO_AVAILABLE:
            try:   self.vehicle_model   = YOLO('yolov8n.pt')
            except: pass
            try:   self.ambulance_model = YOLO('best.pt')
            except: pass

    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def get_frame(self):
        with self._lock:
            return self._frame

    def get_density(self):
        return self.density

    def _should_pause(self):
        """Pause this lane's video processing if the signal is red."""
        signal = self.logic_manager.get_signal(self.lane_id)
        return signal == 'red'

    # ── Main loop ──────────────────────────────────────────────────────
    def _run(self):
        cap = cv2.VideoCapture(self.video_path) if self.video_path else None
        real = cap and cap.isOpened() and YOLO_AVAILABLE and self.vehicle_model
        if real:
            self._run_real(cap)
        else:
            if cap:
                cap.release()
            self._run_sim()

    def _run_real(self, cap):
        last_raw_frame = None
        while self._running:
            if self._should_pause() and last_raw_frame is not None:
                self._process_frame(last_raw_frame.copy())
                time.sleep(0.2)
                continue
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            frame = cv2.resize(frame, (640, 360))
            last_raw_frame = frame.copy()
            self._process_frame(frame)
        cap.release()

    def _process_frame(self, frame):
        cars = buses = trucks = motos = ambs = peds = 0
        amb_flag = ped_flag = False

        # Vehicle + pedestrian via YOLOv8n
        results = self.vehicle_model(frame, verbose=False)[0]
        for box in results.boxes:
            cls  = int(box.cls[0])
            conf = float(box.conf[0])
            if conf < 0.35:
                continue
            x1, y1, x2, y2 = map(int, box.xyxy[0])

            if cls in VEHICLE_CLS:
                lbl = f"{VEHICLE_CLS[cls]} {conf:.2f}"
                col = COLORS[VEHICLE_CLS[cls]]
                cv2.rectangle(frame, (x1,y1),(x2,y2), col, 2)
                cv2.putText(frame, lbl, (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255,255,255), 1)
                if cls == CLS_CAR:   cars  += 1
                elif cls == CLS_MOTO: motos += 1
                elif cls == CLS_BUS:  buses += 1
                elif cls == CLS_TRUCK: trucks += 1

            elif cls == CLS_PERSON and conf >= 0.4:
                peds     += 1
                ped_flag  = True
                cv2.rectangle(frame, (x1,y1),(x2,y2), COLORS['Person'], 2)
                cv2.putText(frame, f"Person {conf:.2f}", (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, COLORS['Person'], 1)

        # Ambulance via custom model
        if self.ambulance_model:
            amb_res = self.ambulance_model(frame, verbose=False)[0]
            for box in amb_res.boxes:
                conf = float(box.conf[0])
                if conf >= 0.4:
                    ambs    += 1
                    amb_flag = True
                    x1,y1,x2,y2 = map(int, box.xyxy[0])
                    cv2.rectangle(frame,(x1,y1),(x2,y2),(0,0,255),3)
                    cv2.putText(frame,f"EMERGENCY {conf:.2f}",(x1,y1-5),cv2.FONT_HERSHEY_SIMPLEX,0.6,(0,0,255),2)

        density = cars + buses + trucks + motos
        self._update(cars, buses, trucks, motos, ambs, peds, amb_flag, ped_flag, density, frame)

    def _update(self, cars, buses, trucks, motos, ambs, peds, amb_flag, ped_flag, density, frame):
        self.cars = cars; self.buses = buses; self.trucks = trucks
        self.motorcycles = motos; self.ambulances = ambs; self.pedestrians = peds
        self.density = density
        self.ambulance_detected  = amb_flag
        self.pedestrian_detected = ped_flag
        self.logic_manager.update_lane(
            self.lane_id, density, amb_flag, ped_flag,
            cars, buses, trucks, motos, ambs, peds)
        self._annotate_overlay(frame, density, amb_flag, ped_flag)

    def _annotate_overlay(self, frame, density, amb_flag, ped_flag):
        signal   = self.logic_manager.get_signal(self.lane_id)
        sig_col  = {'green':(0,200,0),'yellow':(0,200,200),'red':(50,50,200)}
        gt       = self.logic_manager.get_green_time(self.lane_id)
        # header bar
        cv2.rectangle(frame, (0,0),(640,28),(20,20,30),-1)
        cv2.putText(frame, f"Lane {self.lane_id}", (8,20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)
        # status bar
        cv2.rectangle(frame,(0,332),(640,360),(20,20,30),-1)
        parts = [f"D:{density}", f"Amb:{'YES' if amb_flag else 'No'}",
                 f"Ped:{'YES' if ped_flag else 'No'}", f"T:{int(gt)}s"]
        cv2.putText(frame, '  |  '.join(parts), (6,352),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, sig_col.get(signal,(200,200,200)), 1)
        _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        with self._lock:
            self._frame = buf.tobytes()

    def _run_sim(self):
        base_d = random.randint(3, 20)
        tick   = 0
        last_sim_state = None
        while self._running:
            if self._should_pause() and last_sim_state is not None:
                # Reuse last generated frame and data, but call _update to refresh overlay
                frame_clean, args = last_sim_state
                self._update(*args, frame_clean.copy())
                time.sleep(0.2)
                continue
            
            tick += 1
            frame = np.zeros((360, 640, 3), dtype=np.uint8)
            # Road background
            cv2.rectangle(frame, (0,0),(640,360),(45,55,45),-1)
            # Road lanes
            for y in range(0,360,40):
                cv2.line(frame,(0,y),(640,y),(60,70,60),1)
            for x in range(0,640,80):
                cv2.line(frame,(x,0),(x,360),(60,70,60),1)

            cars    = random.randint(0, max(0,base_d-2))
            motos   = random.randint(0, 3)
            buses   = random.randint(0, 2)
            trucks  = random.randint(0, 1)
            ambs    = 1 if random.random() < 0.04 else 0
            peds    = random.randint(0, 3)
            amb_flag = ambs > 0
            ped_flag = peds > 0
            density  = cars + motos + buses + trucks

            # Draw vehicles
            veh_types = (['Car']*cars + ['Motorcycle']*motos +
                         ['Bus']*buses + ['Truck']*trucks)
            random.shuffle(veh_types)
            for vt in veh_types[:10]:
                x1 = random.randint(10, 520)
                y1 = random.randint(30, 270)
                w  = {'Car':70,'Motorcycle':35,'Bus':110,'Truck':90}[vt]
                h  = {'Car':45,'Motorcycle':28,'Bus':55,'Truck':50}[vt]
                col = COLORS[vt]
                cv2.rectangle(frame,(x1,y1),(x1+w,y1+h),col,2)
                cv2.putText(frame,f"{vt} 0.{random.randint(70,95)}",(x1,y1-4),
                            cv2.FONT_HERSHEY_SIMPLEX,0.38,(230,230,230),1)

            # Pedestrians
            for _ in range(peds):
                px,py = random.randint(30,580), random.randint(30,300)
                cv2.circle(frame,(px,py),10,COLORS['Person'],-1)
                cv2.putText(frame,"Person",(px-15,py-14),cv2.FONT_HERSHEY_SIMPLEX,0.32,COLORS['Person'],1)

            # Ambulance
            if amb_flag:
                ax,ay = random.randint(80,420), random.randint(50,220)
                cv2.rectangle(frame,(ax,ay),(ax+120,ay+65),(0,0,255),3)
                cv2.rectangle(frame,(ax+5,ay+5),(ax+115,ay+60),(50,50,200),-1)
                cv2.putText(frame,"AMBULANCE",(ax+5,ay+40),cv2.FONT_HERSHEY_SIMPLEX,0.55,(255,255,255),2)
                cv2.putText(frame,"0.91",(ax+5,ay+58),cv2.FONT_HERSHEY_SIMPLEX,0.4,(200,200,200),1)

            # Save clean frame before overlay
            args = (cars, buses, trucks, motos, ambs, peds, amb_flag, ped_flag, density)
            last_sim_state = (frame.copy(), args)
            
            self._update(*args, frame)

            base_d = max(1, min(28, base_d + random.randint(-2, 2)))
            time.sleep(0.6)
