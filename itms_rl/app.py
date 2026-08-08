from flask import (Flask, render_template, request, redirect,
                   url_for, session, Response, jsonify)
import sqlite3, os, threading, time, json
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from detector import VideoDetector
from traffic_logic import TrafficLogicManager

app = Flask(__name__)
app.secret_key = 'itms_rl_secret_2024'
# Prevent Flask from sorting mixed-key JSON payloads (int lane keys + meta keys).
app.json.sort_keys = False
UPLOAD_FOLDER = 'uploads'
PHASES_FILE = 'project_phases.json'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def load_project_phases():
    if not os.path.exists(PHASES_FILE):
        return []
    try:
        with open(PHASES_FILE, 'r', encoding='utf-8') as f:
            phases = json.load(f)
        if not isinstance(phases, list):
            return []
        clean = []
        for p in phases:
            if not isinstance(p, dict):
                continue
            phase_no = p.get('phase_no')
            title = p.get('title')
            desc = p.get('desc')
            date = p.get('date')
            status = p.get('status', 'pending')
            if isinstance(phase_no, int) and title and desc and date:
                clean.append({
                    'phase_no': phase_no,
                    'title': str(title),
                    'desc': str(desc),
                    'date': str(date),
                    'status': status if status in ('done', 'current', 'pending') else 'pending'
                })
        clean.sort(key=lambda p: p['phase_no'])
        return clean
    except Exception:
        return []

# ÔöÇÔöÇ DB ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
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

init_db()

# ÔöÇÔöÇ Global state ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
logic_manager = TrafficLogicManager()
detectors: dict = {}
_lock = threading.Lock()
_detection_config = {
    'heuristic_sensitivity': 'strict',
    'emergency_policy': 'custom_only',
    'emergency_conf_threshold': 0.70,
}


def _apply_detection_config_to_detector(det):
    sensitivity = _detection_config.get('heuristic_sensitivity', 'strict')
    emergency_policy = _detection_config.get('emergency_policy', 'custom_only')
    emergency_conf_threshold = _detection_config.get('emergency_conf_threshold', 0.70)
    if hasattr(det, 'set_heuristic_sensitivity'):
        det.set_heuristic_sensitivity(sensitivity)
    if hasattr(det, 'set_emergency_policy'):
        det.set_emergency_policy(emergency_policy)
    if hasattr(det, 'set_emergency_conf_threshold'):
        det.set_emergency_conf_threshold(emergency_conf_threshold)


def _apply_detection_config_to_all_detectors():
    with _lock:
        current = list(detectors.values())
    for det in current:
        _apply_detection_config_to_detector(det)

# ÔöÇÔöÇ Auth ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def _has_users():
    db = get_db()
    row = db.execute('SELECT COUNT(*) as c FROM users').fetchone()
    return bool(row and row['c'] > 0)

@app.route('/', methods=['GET','POST'])
def login():
    if not _has_users():
        return redirect(url_for('signup'))

    error = None
    info = request.args.get('info')
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
    return render_template('login.html', error=error, info=info)

@app.route('/signup', methods=['GET','POST'])
def signup():
    error = None
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        confirm  = request.form.get('confirm_password') or ''

        if len(username) < 3:
            error = 'Username must be at least 3 characters.'
        elif len(password) < 6:
            error = 'Password must be at least 6 characters.'
        elif password != confirm:
            error = 'Passwords do not match.'
        else:
            db = get_db()
            exists = db.execute('SELECT 1 FROM users WHERE username=?', (username,)).fetchone()
            if exists:
                error = 'Username already exists.'
            else:
                role = 'admin' if not _has_users() else 'user'
                db.execute(
                    'INSERT INTO users (username, password, role) VALUES (?,?,?)',
                    (username, generate_password_hash(password), role)
                )
                db.commit()
                return redirect(url_for('login', info='Account created. Please login.'))

    return render_template('signup.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ÔöÇÔöÇ Pages ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
@app.route('/home')
@login_required
def home():
    phases = load_project_phases()
    return render_template('project_home.html', phases=phases)

@app.route('/upload', methods=['GET','POST'])
@login_required
def upload():
    error = None
    if request.method == 'POST':
        simulate_mode = request.form.get('simulation_mode') == '1'

        # Optional: custom emergency model upload (.pt)
        emergency_model_file = request.files.get('emergency_model')
        if emergency_model_file and emergency_model_file.filename:
            model_name = emergency_model_file.filename.lower()
            if not model_name.endswith('.pt'):
                error = 'Emergency model must be a .pt file.'
                return render_template('upload.html', error=error)
            os.makedirs('models', exist_ok=True)
            emergency_model_file.save(os.path.join('models', 'emergency_best.pt'))

        with _lock:
            for d in detectors.values():
                d.stop()
            detectors.clear()
            logic_manager.reset()

        lane_paths = {}
        uploaded_any = False
        for i in range(1, 5):
            f = request.files.get(f'lane{i}')
            path = None
            if f and f.filename:
                fname = secure_filename(f.filename)
                path  = os.path.join(UPLOAD_FOLDER, f'lane{i}_{fname}')
                f.save(path)
                uploaded_any = True
            lane_paths[i] = path

        if not uploaded_any and not simulate_mode:
            logic_manager.set_system_active(False)
            error = 'Upload at least one lane video or enable simulation mode to start.'
            return render_template('upload.html', error=error)

        for i in range(1, 5):
            if not simulate_mode and lane_paths[i] is None:
                continue
            det = VideoDetector(lane_id=i, video_path=lane_paths[i], logic_manager=logic_manager)
            _apply_detection_config_to_detector(det)
            with _lock:
                detectors[i] = det
            det.start()

        logic_manager.set_system_active(True)
        return redirect(url_for('dashboard'))

    return render_template('upload.html', error=error)

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

# ÔöÇÔöÇ API ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
@app.route('/video_feed/<int:lane_id>')
@login_required
def video_feed(lane_id):
    def gen():
        last_frame = None
        while True:
            with _lock:
                det = detectors.get(lane_id)
            signal = logic_manager.get_signal(lane_id)

            sleep_interval = 0.2
            if det:
                # Red: hold the last delivered frame (visual pause).
                # Yellow: update at reduced rate.
                # Green: stream at normal rate.
                if signal == 'red':
                    if last_frame is None:
                        frame = det.get_frame()
                        if frame:
                            last_frame = frame
                    frame_to_send = last_frame
                    sleep_interval = 0.25
                elif signal in ('yellow', 'orange'):
                    frame = det.get_frame()
                    if frame:
                        last_frame = frame
                    frame_to_send = last_frame
                    sleep_interval = 0.12
                else:
                    frame = det.get_frame()
                    if frame:
                        last_frame = frame
                    frame_to_send = last_frame
                    sleep_interval = 0.04

                if frame_to_send:
                    yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame_to_send + b'\r\n'

            time.sleep(sleep_interval)
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/stats_api')
@login_required
def stats_api():
    raw = logic_manager.get_all_stats()
    lanes = {}
    for i in range(1, 5):
        lane_stats = raw.get(i, {})
        lanes[str(i)] = lane_stats

    emergency_model_file_present = any(
        os.path.exists(p) for p in ('best.pt', 'models/best.pt', 'models/emergency_best.pt')
    )
    with _lock:
        detector_list = list(detectors.values())
    emergency_model_loaded = any(
        getattr(det, 'emergency_model_loaded', False) for det in detector_list
    ) if detector_list else emergency_model_file_present
    emergency_mode = 'none'
    emergency_model_path = None
    for det in detector_list:
        mode = getattr(det, 'emergency_detection_mode', 'none')
        if mode == 'custom_model':
            emergency_mode = 'custom_model'
            emergency_model_path = getattr(det, 'emergency_model_path', None)
            break
        if mode == 'heuristic' and emergency_mode == 'none':
            emergency_mode = 'heuristic'

    return jsonify({
        'lanes': lanes,
        'weather': raw.get('weather', {}),
        'decision_mode': raw.get('decision_mode', 'initializing'),
        'system_active': raw.get('system_active', False),
        'models': {
            'emergency_model_file_present': emergency_model_file_present,
            'emergency_model_loaded': emergency_model_loaded,
            'emergency_detection_mode': emergency_mode,
            'emergency_model_path': emergency_model_path,
        },
        'config': {
            'heuristic_sensitivity': _detection_config.get('heuristic_sensitivity', 'medium')
        },
        'rl': raw.get('rl', {}),
        'cycle': raw.get('cycle', 0),
    })


@app.route('/config_api', methods=['GET', 'POST'])
@login_required
def config_api():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        sensitivity = data.get('heuristic_sensitivity', _detection_config.get('heuristic_sensitivity'))
        emergency_policy = data.get('emergency_policy', _detection_config.get('emergency_policy'))
        emergency_conf_threshold = data.get('emergency_conf_threshold', _detection_config.get('emergency_conf_threshold'))

        if sensitivity not in ('strict', 'medium', 'high'):
            return jsonify({'ok': False, 'error': 'Invalid heuristic_sensitivity'}), 400
        if emergency_policy not in ('custom_only', 'hybrid', 'heuristic_only'):
            return jsonify({'ok': False, 'error': 'Invalid emergency_policy'}), 400
        try:
            emergency_conf_threshold = float(emergency_conf_threshold)
        except (TypeError, ValueError):
            return jsonify({'ok': False, 'error': 'Invalid emergency_conf_threshold'}), 400
        if not (0.30 <= emergency_conf_threshold <= 0.95):
            return jsonify({'ok': False, 'error': 'emergency_conf_threshold must be between 0.30 and 0.95'}), 400

        _detection_config['heuristic_sensitivity'] = sensitivity
        _detection_config['emergency_policy'] = emergency_policy
        _detection_config['emergency_conf_threshold'] = round(emergency_conf_threshold, 2)
        _apply_detection_config_to_all_detectors()
        return jsonify({'ok': True, 'config': _detection_config})

    return jsonify({
        'ok': True,
        'config': _detection_config,
        'options': {
            'heuristic_sensitivity': ['strict', 'medium', 'high'],
            'emergency_policy': ['custom_only', 'hybrid', 'heuristic_only']
        }
    })

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
                counts[i] = {
                    'cars':        det.cars,
                    'buses':       det.buses,
                    'trucks':      det.trucks,
                    'motorcycles': det.motorcycles,
                    'ambulances':  det.ambulances,
                    'pedestrians': det.pedestrians,
                    'density':     det.density,
                }
            else:
                counts[i] = {'cars':0,'buses':0,'trucks':0,'motorcycles':0,'ambulances':0,'pedestrians':0,'density':0}
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
