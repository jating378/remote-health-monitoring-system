from flask import Flask, render_template, jsonify, request
import threading
import pandas as pd
import numpy as np
import random
import time
import os
from datetime import datetime
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

DATA_DIR = "data"
CSV_FILE = os.path.join(DATA_DIR, "patient_readings.csv")
ALERTS_FILE = os.path.join(DATA_DIR, "alerts_log.csv")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

class Patient:
    def __init__(self, pid):
        self.pid = pid
        self.spo2 = random.uniform(95.0, 99.0)
        self.history = []
        self.low_reading_count = 0
        self.thresholds = {
            'warning': 95.0,
            'critical': 90.0,
            'ml_boundary': None
        }
        self.current_alert = None
        self.alert_active = False
        self.last_alert_time = None

    def update_thresholds(self):
        if len(self.history) >= 50 and len(self.history) % 50 == 0:
            recent_values = np.array([x['spo2'] for x in self.history[-50:]])
            mean_val = np.mean(recent_values)
            std_dev = np.std(recent_values)

            self.thresholds['warning'] = max(mean_val - 2, 85.0)
            self.thresholds['critical'] = max(mean_val - 5, 80.0)
            self.thresholds['ml_boundary'] = mean_val - 1.5 * std_dev  # More dynamic ML-based threshold

    def generate_reading(self):
        if self.current_alert == "assistance provided" and self.spo2 < 95:
            delta = random.uniform(0.3, 0.5)
        elif self.alert_active:
            delta = -random.uniform(0.4, 0.8)
        else:
            if random.random() < 0.005:
                delta = -random.uniform(1.5, 3.0)
            else:
                delta = random.gauss(0, 0.2)

        self.spo2 = np.clip(self.spo2 + delta, 70.0, 100.0)
        reading = {
            'timestamp': datetime.now().replace(microsecond=0).isoformat(),
            'spo2': self.spo2,
            'thresholds': self.thresholds.copy()
        }

        self.history.append(reading)
        self.update_thresholds()
        self.detect_conditions()
        self.save_to_csv(reading)
        return reading

    def detect_conditions(self):
        if self.current_alert == "assistance provided":
            if self.spo2 >= 95:
                self.clear_alert("RECOVERY: Patient is stable again.")
            return  

        latest_spo2 = self.spo2
        new_alert = None

        if latest_spo2 < 90:
            new_alert = "critical"
        elif latest_spo2 < self.thresholds['warning']:
            self.low_reading_count += 1
            if self.low_reading_count >= 2:
                new_alert = "warning"
        else:
            self.low_reading_count = 0

        if new_alert and self.current_alert != new_alert:
            self.current_alert = new_alert
            self.alert_active = True
            self.last_alert_time = time.time()
            if new_alert == "critical":
                trigger_alert(self.pid, "CRITICAL ALERT: Immediate attention needed!")
            elif new_alert == "warning":
                trigger_alert(self.pid, "ALERT: SpO₂ dropping, monitor closely!")

        # Auto-clear alerts after 3 minutes if patient stabilizes
        if self.alert_active and self.last_alert_time and (time.time() - self.last_alert_time > 180):
            if self.spo2 > 94:
                self.clear_alert("AUTO RECOVERY: Patient has stabilized.")

    def clear_alert(self, message):
        self.current_alert = None
        self.alert_active = False
        trigger_alert(self.pid, message, clear=True)

    def save_to_csv(self, reading):
        df = pd.DataFrame([{
            'pid': self.pid,
            'timestamp': reading['timestamp'],
            'spo2': reading['spo2'],
            'warning_threshold': self.thresholds['warning'],
            'critical_threshold': self.thresholds['critical'],
            'ml_boundary': self.thresholds['ml_boundary']
        }])
        df.to_csv(CSV_FILE, mode='a', header=not os.path.exists(CSV_FILE), index=False)

def trigger_alert(patient_id, message, clear=False):
    alert_data = {
        "timestamp": datetime.now().replace(microsecond=0).isoformat(),
        "patient_id": patient_id,
        "message": message
    }
    socketio.emit('alert', alert_data)

    if clear:
        socketio.emit('alert_clear', {'patient_id': patient_id})

    log_alert(alert_data)

def log_alert(alert_data):
    df = pd.DataFrame([alert_data])
    df.to_csv(ALERTS_FILE, mode='a', header=not os.path.exists(ALERTS_FILE), index=False)

patients = {f"P{i+1}": Patient(f"P{i+1}") for i in range(5)}

def simulation_thread():
    while True:
        for patient in patients.values():
            patient.generate_reading()
        time.sleep(2)

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/data')
def get_data():
    data = {}
    for pid, patient in patients.items():
        if patient.history:
            latest = patient.history[-1]
            latest['status'] = (
                patient.current_alert if patient.alert_active else "normal"
            )
            latest['alert_active'] = patient.alert_active
            latest['ml_score'] = patient.thresholds['ml_boundary']
            data[pid] = latest
    return jsonify(data)

@app.route('/api/acknowledge/<pid>', methods=['POST'])
def acknowledge_alert(pid):
    if pid in patients:
        patient = patients[pid]
        patient.current_alert = "assistance provided"
        patient.alert_active = True
        patient.last_alert_time = time.time()
        trigger_alert(pid, "ASSISTANCE PROVIDED: Alert acknowledged. Patient recovery initiated.")
        return jsonify({"status": "success", "message": f"Alert for {pid} acknowledged; recovery initiated."})
    return jsonify({"status": "error", "message": "Patient not found."}), 404

if __name__ == '__main__':
    threading.Thread(target=simulation_thread, daemon=True).start()
    socketio.run(app, port=5000, debug=True)
