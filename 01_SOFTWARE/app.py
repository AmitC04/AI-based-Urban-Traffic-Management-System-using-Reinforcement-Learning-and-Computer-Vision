from flask import (Flask, render_template, request, redirect,
                   url_for, session, Response, jsonify)
import sqlite3, os, threading, time
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from detector import VideoDetector
from traffic_logic import TrafficLogicManager

app = Flask(__name__)
app.secret_key = 'itms_rl_secret_2024'
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ── DB ─────────────────────────────────────────────────────────────────
def get_db():
    db = sqlite3.connect('users.db')
    db.row_factory = sqlite3.Row
    return db

def init_db():
    with get_db() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS users
            (id INTEGER PRIMARY KEY, username TEXT UNIQUE,
             password TEXT, role TEXT DEFAULT "user")''')
        db.execute('''CREATE TABLE IF NOT EXISTS traffic_log
            (id INTEGER PRIMARY KEY, lane INTEGER,
             cars INTEGER, buses INTEGER, trucks INTEGER,
             motorcycles INTEGER, ambulances INTEGER,
             pedestrians INTEGER DEFAULT 0,
             total INTEGER, green_time REAL,
             decision_mode TEXT DEFAULT "unknown",
             timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        try:
            db.execute("INSERT INTO users (username,password,role) VALUES (?,?,?)",
                ('traffic-admin', generate_password_hash('admin123'), 'admin'))
            db.commit()
        except: pass

init_db()

# ── Global state ───────────────────────────────────────────────────────
logic_manager = TrafficLogicManager()
detectors: dict = {}
_lock = threading.Lock()

# ── Auth ───────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/', methods=['GET','POST'])
def login():
    error = None
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username=?',(u,)).fetchone()
        if user and check_password_hash(user['password'], p):
            session['user'] = u
            session['role'] = user['role']
            return redirect(url_for('home'))
        error = 'Invalid credentials'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ── Pages ──────────────────────────────────────────────────────────────
@app.route('/home')
@login_required
def home():
    return render_template('project_home.html')

@app.route('/upload', methods=['GET','POST'])
@login_required
def upload():
    if request.method == 'POST':
        with _lock:
            for d in detectors.values(): d.stop()
            detectors.clear()
            logic_manager.reset()
        for i in range(1, 5):
            f = request.files.get(f'lane{i}')
            path = None
            if f and f.filename:
                fname = secure_filename(f.filename)
                path  = os.path.join(UPLOAD_FOLDER, f'lane{i}_{fname}')
                f.save(path)
            det = VideoDetector(lane_id=i, video_path=path, logic_manager=logic_manager)
            with _lock:
                detectors[i] = det
            det.start()
        return redirect(url_for('dashboard'))
    return render_template('upload.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/analysis')
@login_required
def analysis():
    return render_template('analysis.html')

@app.route('/rl_monitor')
@login_required
def rl_monitor():
    return render_template('rl_monitor.html')

# ── API ────────────────────────────────────────────────────────────────
@app.route('/video_feed/<int:lane_id>')
@login_required
def video_feed(lane_id):
    def gen():
        while True:
            with _lock:
                det = detectors.get(lane_id)
            if det:
                frame = det.get_frame()
                if frame:
                    yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
            time.sleep(0.04)
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/stats_api')
@login_required
def stats_api():
    return jsonify(logic_manager.get_all_stats())

@app.route('/rl_api')
@login_required
def rl_api():
    return jsonify(logic_manager.agent.get_status())

@app.route('/live_counts')
@login_required
def live_counts():
    """Returns real-time per-lane vehicle counts directly from detectors."""
    with _lock:
        counts = {}
        for i in range(1, 5):
            det = detectors.get(i)
            if det:
                counts[str(i)] = {
                    'cars':        det.cars,
                    'buses':       det.buses,
                    'trucks':      det.trucks,
                    'motorcycles': det.motorcycles,
                    'ambulances':  det.ambulances,
                    'pedestrians': det.pedestrians,
                    'density':     det.density,
                }
            else:
                counts[str(i)] = {'cars':0,'buses':0,'trucks':0,'motorcycles':0,'ambulances':0,'pedestrians':0,'density':0}
    return jsonify(counts)

@app.route('/analysis_data')
@login_required
def analysis_data():
    db = get_db()
    lanes = {}
    for i in range(1, 5):
        row = db.execute(
            '''SELECT SUM(cars) cars, SUM(buses) buses, SUM(trucks) trucks,
                      SUM(motorcycles) motorcycles, SUM(ambulances) ambulances,
                      SUM(pedestrians) pedestrians, SUM(total) total
               FROM traffic_log WHERE lane=?''', (i,)).fetchone()
        lanes[f'Lane {i}'] = {
            'cars':        row['cars']        or 0,
            'buses':       row['buses']       or 0,
            'trucks':      row['trucks']      or 0,
            'motorcycles': row['motorcycles'] or 0,
            'ambulances':  row['ambulances']  or 0,
            'pedestrians': row['pedestrians'] or 0,
            'total':       row['total']       or 0,
        }
    # live density from detectors
    density = {}
    with _lock:
        for i in range(1, 5):
            det = detectors.get(i)
            density[f'Lane {i}'] = det.get_density() if det else 0
    # green times
    green_times = {}
    for i in range(1, 5):
        green_times[f'Lane {i}'] = round(logic_manager.get_green_time(i), 1)

    # decision mode counts from DB (real logged data)
    dm_rows = db.execute(
        '''SELECT decision_mode, COUNT(*) cnt FROM traffic_log
           WHERE decision_mode IS NOT NULL AND decision_mode != 'unknown'
           GROUP BY decision_mode ORDER BY cnt DESC''').fetchall()
    decision_modes = {r['decision_mode']: r['cnt'] for r in dm_rows}

    # also include current live mode from RL agent memory
    live_mode = logic_manager._decision_mode
    if live_mode and live_mode not in ('initializing',):
        decision_modes[live_mode] = decision_modes.get(live_mode, 0)

    # wait times per lane (live)
    wait_times = {}
    for i in range(1, 5):
        stats = logic_manager.get_all_stats()
        wait_times[f'Lane {i}'] = stats.get(i, {}).get('wait_time', 0)

    return jsonify({
        'lanes': lanes,
        'density': density,
        'green_times': green_times,
        'decision_modes': decision_modes,
        'wait_times': wait_times,
    })

if __name__ == '__main__':
    app.run(debug=True, threaded=True)
