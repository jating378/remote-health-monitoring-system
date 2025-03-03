# Import required libraries
from flask import Flask, render_template, jsonify
import threading
import pandas as pd
import numpy as np
import random
import time
import os
from datetime import datetime
import csv
import math
from flask_socketio import SocketIO, emit
from sklearn.ensemble import IsolationForest
import numpy as np
import random
import math
from datetime import datetime, timedelta
from flask import request

# Create a Flask web server
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

DATA_DIR = "data"
CSV_FILE = os.path.join(DATA_DIR, "patient_readings.csv")
ALERT_LOG_CSV = "alert_log.csv"

# Global variables for simulation control
simulation_running = True
patients_lock = threading.Lock()

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)


# Patient Class to simulate patient data and alerts 

class Patient:
    def __init__(self, pid):
        
        # Initialize patient data
        self.pid = pid
        self.start_time = datetime.now()

        # Initialize SpO₂ values and thresholds
        self.spo2 = random.uniform(95.0, 99.9)
        self.thresholds = {
            'warning': 95.0,
            'critical': 90.0,
            'ml_boundary': None
        }
        
        # Initialize heart rate values and thresholds
        self.heartrate = random.randint(60, 100)

        self.heartrate_thresholds = {
            'warning_low': 50,
            'critical_low': 40,
            'warning_high': 120,
            'critical_high': 150,
            'ml_boundary': None,
            'ml_boundary_high': None

        }

        # Initialize alert flags and cooldown timer for alerts and assistance
        self.heartrate_alert_active = False
        self.heartrate_current_alert = None
        self.current_alert = None
        self.alert_active = False
        self.last_alert_time = None
        self.cooldown_active = False  # New flag
        self.heartrate_cooldown_active = False
        self.cooldown_end_time = None


        # Initialize ML model and history data for anomaly detection

        self.history = []  # Maintain last 200 readings
        self.heartrate_history = []  # Maintain last 200 readings
        self.low_reading_count = 0
        self.model = None
        self.heartrate_model = None  
        self.trained = False
        
        #initialize flags for increasing and decreasing values used in generating readings
        self.decreasing = False
        self.increasing_heartrate = False
        self.increase_heartrate_counter = 0  # Counter for increasing every 5 readings    
        self.decreasing_heartrate = False
        self.decrease_counter = 0  # Counter for decreasing every 5 readings
        self.decrease_heartrate_counter = 0
        
        
        

    def detect_anomaly(self, spo2_value):
        if self.model is not None:
                prediction = self.model.predict([[spo2_value]])[0]
                return bool(prediction == -1)
        return False

    def detect_heartrate_anomaly(self, heartrate_value):
            """Use Isolation Forest to detect heart rate anomalies."""
            if self.heartrate_model is not None:
                prediction = self.heartrate_model.predict([[heartrate_value]])[0]
                return bool(prediction == -1)
            return False


    # Machine Learning Model Training for ML Based Dynamic Thresholds in spo2 and Heart Rate values

    def train_isolation_forest(self):

        #  ML Model is trained after collecting 50 readings.

        history_size = len(self.history)
        history_size_heartrate = len(self.heartrate_history)
       
        if self.trained:
            return

        if history_size < 50 and history_size_heartrate < 50:
            return  # if Not enough data

        print(f"[TRAINING] {self.pid} Training ML Model...")  # Confirm training start
        data = np.array([x['spo2'] for x in self.history])
        heartrate_data = np.array([x['heartrate'] for x in self.heartrate_history])
        
       
        ml_threshold = float(np.percentile(data, 5))
        ml_threshold_heartrate = float(np.percentile(heartrate_data, 5))
        ml_threshold_heartrate_high = float(np.percentile(heartrate_data, 95))


        self.thresholds['ml_boundary'] = ml_threshold
        self.heartrate_thresholds['ml_boundary'] = ml_threshold_heartrate
        self.heartrate_thresholds['ml_boundary_high'] = ml_threshold_heartrate_high

        self.model = IsolationForest(contamination=0.1, random_state=42)
        self.model.fit(data.reshape(-1, 1))
        
        self.heartrate_model = IsolationForest(contamination=0.1, random_state=42)
        self.heartrate_model.fit(heartrate_data.reshape(-1, 1))

        self.trained = True  # Mark as trained


        print(f"[TRAINED] {self.pid} ML Thresholds: {self.thresholds}")



    
        


    # Generate SpO₂ readings with realistic fluctuations

    def generate_reading(self):

        now = datetime.now()

        # Stop decreasing, start increasing if cooldown is active
        if self.cooldown_active:
            self.decreasing = False
            if now >= self.cooldown_end_time:
                self.cooldown_active = False  # Cooldown over
            else:
                # Gradually increase SpO₂ towards 97%
                self.spo2 = min(self.spo2 + random.uniform(0.1, 0.2), 99.0)
                return  
            

        # Simulate SpO₂ readings with anomaly chances and gradual changes
        if not self.decreasing and random.random() < 0.005:
            self.decreasing = True
            self.decrease_counter = 0

        if self.decreasing:
            self.decrease_counter += 1
            if self.decrease_counter % 5 == 0:  
                delta = -random.uniform(0.2, 0.5)
            else:delta = random.gauss(0, 0.02)  
        else:
            delta = random.gauss(0.01, 0.03)

        self.spo2 = np.clip(self.spo2 + delta, 70.0, 100.0)
        reading = {
            'timestamp': datetime.now().replace(microsecond=0).isoformat(),
            'spo2': self.spo2,
            'thresholds': self.thresholds.copy()
        }

        # Maintain rolling window of 50 readings for ML model
        self.history.append(reading)
        if len(self.history) > 50:
            self.history.pop(0)

        self.train_isolation_forest()
        
        self.save_to_csv(reading)
        return reading
    

    # Generate Heart Rate readings with realistic fluctuations

    def generate_reading_heartrate(self):
        now = datetime.now()

        # Stop decreasing or increasing if cooldown ( after alert acknowledgment )is active
        if self.heartrate_cooldown_active:
            self.decreasing_heartrate = False
            self.increasing_heartrate = False
            if now >= self.cooldown_end_time:
                self.heartrate_cooldown_active = False  
            else:
                if self.heartrate < 85:
                    self.heartrate = int(min(self.heartrate + random.uniform(0.5, 1.5), 85))
                elif self.heartrate > 85:
                    self.heartrate = int(max(self.heartrate - random.uniform(0.5, 1.5), 85))
                return  

        # Heartbeat simulation using sine wave pattern
        time_elapsed = (now - self.start_time).total_seconds()
        heart_rate_base = 75  # Normal resting heart rate
        heart_rate_amplitude = 1 # Variation amplitude
        heart_rate_fluctuation = random.gauss(0, 0.5)  # Random fluctuation

        # Slower sine wave variation (cycle every 120 seconds)
        delta = heart_rate_amplitude * math.sin(2 * math.pi * time_elapsed / 120) + heart_rate_fluctuation

        # Apply gradual increasing or decreasing logic with 0.005 probability (choose only one)
        if not self.decreasing_heartrate and not self.increasing_heartrate:
            if random.random() < 0.005:
                if random.choice([True, False]):  # Randomly choose increasing or decreasing
                    self.increasing_heartrate = True
                    self.increase_heartrate_counter = 0
                else:
                    self.decreasing_heartrate = True
                    self.decrease_heartrate_counter = 0

        # Handle decreasing logic
        if self.decreasing_heartrate:
            self.decrease_heartrate_counter += 1
            if self.decrease_heartrate_counter % 10 == 0:  # Decrease less frequently
                delta -= random.uniform(1, 3)

        # Handle increasing logic
        elif self.increasing_heartrate:  # Use `elif` to ensure only one applies
            self.increase_heartrate_counter += 1
            if self.increase_heartrate_counter % 10 == 0:  # Increase less frequently
                delta += random.uniform(1, 3)


        # Keep stable if neither increasing nor decreasing
        if not self.decreasing_heartrate and not self.increasing_heartrate:
            delta = random.choice([-2, -1, 0, 1, 2])  # Small variation

        # Apply change and clip within a realistic range
        self.heartrate = int(np.clip(self.heartrate + delta, 30, 180))  # Heart rate range: 30-180 BPM

        # Stop increasing/decreasing after a while
        if self.decreasing_heartrate and self.heartrate <= 50:
            self.decreasing_heartrate = False  # Reset decreasing state
        if self.increasing_heartrate and self.heartrate >= 130:
            self.increasing_heartrate = False  # Reset increasing state

        # Create reading
        reading = {
            'timestamp': now.replace(microsecond=0).isoformat(),
            'heartrate': self.heartrate,
            'thresholds': self.heartrate_thresholds.copy()
        }

        # Maintain rolling window of 50 readings
        self.heartrate_history.append(reading)
        if len(self.heartrate_history) > 50:
            self.heartrate_history.pop(0)


        return reading

    
    # Save readings to CSV file for storing patient data
    def save_to_csv(self, reading):
        df = pd.DataFrame([{
            'pid': self.pid,
            'timestamp': reading['timestamp'],
            'spo2': self.spo2,
            'heartrate': self.heartrate,
            'warning_threshold': self.thresholds['warning'],
            'critical_threshold': self.thresholds['critical'],
            'warning_low_threshold_heartrate': self.heartrate_thresholds['warning_low'],
            'critical_low_threshold_heartrate': self.heartrate_thresholds['critical_low'],
            'warning_high_threshold_heartrate': self.heartrate_thresholds['warning_high'],
            'critical_high_threshold_heartrate': self.heartrate_thresholds['critical_high'],
            'ml_boundary': self.thresholds['ml_boundary'],
            'ml_boundary_heartrate': self.heartrate_thresholds['ml_boundary'],
            'ml_boundary_high_heartrate': self.heartrate_thresholds['ml_boundary_high']
        }])
        df.to_csv(CSV_FILE, mode='a', header=not os.path.exists(CSV_FILE), index=False)



# API Function for logging alerts to a CSV file
# Ensure the CSV file has headers if it doesn't exist
def initialize_csv():
    try:
        with open(ALERT_LOG_CSV, mode='x', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Patient ID", "Timestamp", "Event", "Status", "Alert Message"])
    except FileExistsError:
        pass

initialize_csv()

def log_alert_event(patient_id, event, status, alert_message):
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(ALERT_LOG_CSV, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([patient_id, timestamp, event, status, alert_message])

@app.route('/api/log_alert', methods=['POST'])
def log_alert():
    
    data = request.json
    patient_id = data.get("patient_id")
    alert_message = data.get("alert_message", "No message")
    status = data.get("status", "active")
    
    log_alert_event(patient_id, "ALERT", status, alert_message)
    return jsonify({"message": f"Alert for Patient {patient_id} logged."})



# Initialize 5 patients for simulation with unique IDs for demonstration purposes
patients = {f"P{i+1}": Patient(f"P{i+1}") for i in range(6)}


# Function to simulate patient data and send updates to the dashboard
def simulation_thread():
    while True:
        if simulation_running:
            with patients_lock:  
                updates = []

                # Send initial readings when restarting
                if not hasattr(simulation_thread, "initial_sent"):
                    for patient in patients.values():
                        socketio.emit('update_spo2', {
                            'patient_id': patient.pid,
                            'spo2': patient.spo2,
                            'heartrate': patient.heartrate,
                            'timestamp': datetime.now().replace(microsecond=0).isoformat()
                        })
                    simulation_thread.initial_sent = True
                
                # Generate new readings
                for patient in patients.values():
                    patient.generate_reading()
                    patient.generate_reading_heartrate()
                    updates.append({
                        'patient_id': patient.pid,
                        'spo2': patient.spo2,
                        'heartrate': float(patient.heartrate),
                        'timestamp': datetime.now().replace(microsecond=0).isoformat()
                    })
                
                # Send updates
                for update in updates:
                    socketio.emit('update_spo2', update)
            
            time.sleep(1)
        else:
            
            if hasattr(simulation_thread, "initial_sent"):
                del simulation_thread.initial_sent
            time.sleep(1)


# API Endpoint for sending patient data to the dashboard and logics for alerts and assistance

@app.route('/api/data')
def get_data():
    data = {}
    with patients_lock:
        for pid, patient in patients.items():

            # Default status and alert messages for SpO₂ and Heart Rate
            status_text = "Normal"
            status_class = "Normal"
            hr_status_class = "Normal"
            hr_status_text = "Normal"

            # ML-based anomaly detection thresholds
            ml_boundary = patient.thresholds.get('ml_boundary', None)
            hr_ml_boundary = patient.heartrate_thresholds.get('ml_boundary', None)
            hr_ml_boundary_high = patient.heartrate_thresholds.get('ml_boundary_high', None)

            
            # Check for SpO₂ anomalies
            
            if ml_boundary is not None and patient.spo2 < ml_boundary:
                    
                    # SpO₂ below ML boundary
                    if patient.spo2 < patient.thresholds['critical']:
                        status_class = "Critical"
                        status_text = "ML Detected Anomaly -  Low SpO2 Critical"
                        patient.alert_active = True
                    elif patient.spo2 < patient.thresholds['warning']:
                        status_class = "Warning"
                        status_text = "ML Detected Anomaly -  Low SpO2 Warning"
                        patient.alert_active = True
                    else :
                        status_class = "Normal"
                        status_text = "Decrease/Baseline Shift Detected in SpO2 ( under ML observation )"
            else:
                    # SpO₂ within defined thresholds until ML boundary is calculated
                    if patient.spo2 < patient.thresholds['critical']:
                        status_class = "Critical"
                        status_text = "Critical -  Low SpO2 "
                        patient.alert_active = True
                    elif patient.spo2 < patient.thresholds['warning']:
                        status_class = "Warning"
                        status_text = "Warning - Low SpO2 "
                        patient.alert_active = True
                

            # Update alert message if active
            if patient.alert_active:
                patient.current_alert = status_text

            
            # Check for Heart Rate anomalies

            if hr_ml_boundary is not None and (patient.heartrate < hr_ml_boundary or patient.heartrate > hr_ml_boundary_high):
                # Heart rate anomaly detected by ML boundary
                if patient.heartrate < patient.heartrate_thresholds['critical_low'] or patient.heartrate > patient.heartrate_thresholds['critical_high']:
                    hr_status_class = "Critical"
                    hr_status_text = "ML Detected Unusual Fluctuation   - Heart Rate Critical"
                    patient.heartrate_alert_active = True
                elif patient.heartrate < patient.heartrate_thresholds['warning_low'] or patient.heartrate > patient.heartrate_thresholds['warning_high']:
                    hr_status_class = "Warning"
                    hr_status_text = "ML Detected Unusual Fluctuation - Heart Rate Warning "
                    patient.heartrate_alert_active = True
                else:
                    hr_status_class = "Normal"
                    hr_status_text = "ML Detected Unusual Fluctuation - Heart Rate Normal but under ML observation )"
                
            else:
                # Heart rate outside ML boundary but within defined thresholds
                if patient.heartrate < patient.heartrate_thresholds['critical_low'] or patient.heartrate > patient.heartrate_thresholds['critical_high']:
                    hr_status_class = "Critical"
                    hr_status_text = "Critical - Heart Rate"
                    patient.heartrate_alert_active = True
                elif patient.heartrate < patient.heartrate_thresholds['warning_low'] or patient.heartrate > patient.heartrate_thresholds['warning_high']:
                    hr_status_class = "Warning"
                    hr_status_text = "Warning - Heart Rate"
                    patient.heartrate_alert_active = True
            
            # Update alert message if active
            if patient.heartrate_alert_active:
                patient.heartrate_current_alert = hr_status_text


            # Check for cooldown status and update alert status
            if patient.cooldown_active :
                status_class = "assistance-active"
                status_text = "Assistance in Progress"
            if patient.heartrate_cooldown_active:
                hr_status_class = "assistance-active"
                hr_status_text = "Assistance in Progress"

            # Prepare API Response
            data[pid] = {
                "timestamp": datetime.now().replace(microsecond=0).isoformat(),
                "spo2": round(patient.spo2, 1),
                "heartrate": round(patient.heartrate, 1),
                "thresholds": {
                    "warning": round(patient.thresholds['warning'], 1),
                    "critical": round(patient.thresholds['critical'], 1),
                    "ml_boundary": round(ml_boundary, 1) if ml_boundary is not None else "CALCULATING",
                    "heartrate_warning_low": round(patient.heartrate_thresholds['warning_low'], 1),
                    "heartrate_critical_low": round(patient.heartrate_thresholds['critical_low'], 1),
                    "heartrate_warning_high": round(patient.heartrate_thresholds['warning_high'], 1),
                    "heartrate_critical_high": round(patient.heartrate_thresholds['critical_high'], 1),
                    "heartrate_ml_boundary": round(hr_ml_boundary, 1) if hr_ml_boundary is not None else "CALCULATING",
                    "heartrate_ml_boundary_high": round(hr_ml_boundary_high, 1) if hr_ml_boundary_high is not None else "CALCULATING"
                },
                "status": status_class,
                "alert_active": patient.alert_active,
                "current_alert": patient.current_alert,
                "spo2_ml_anomaly": bool(patient.trained and patient.spo2 < patient.thresholds['ml_boundary'])
                if patient.thresholds['ml_boundary'] is not None else False,
                "heartrate_status": hr_status_class,
                "heartrate_alert_active": patient.heartrate_alert_active,
                "heartrate_current_alert": patient.heartrate_current_alert,
                "heartrate_ml_anomaly": bool(patient.trained and patient.heartrate < patient.heartrate_thresholds['ml_boundary'])
                if patient.heartrate_thresholds['ml_boundary'] is not None else False,
            }

            

    return jsonify(data)







# API Endpoints for acknowledging alerts and starting recovery mode

@app.route('/api/acknowledge_alert/<pid>', methods=['POST'])
def acknowledge_alert(pid):
    
    log_alert_event(pid, "ASSISTANCE", "acknowledged", "Assistance provided to patient")

    # Handle patient cooldown logic
    if pid in patients:
        patient = patients[pid]
        if patient.alert_active or patient.heartrate_alert_active:
            patient.alert_active = False
            patient.current_alert = None
            patient.heartrate_alert_active = False
            patient.heartrate_current_alert = None
            patient.cooldown_active = True
            patient.heartrate_cooldown_active = True
            patient.cooldown_end_time = datetime.now() + timedelta(seconds=30)


        return jsonify({"message": f"Alert for {pid} acknowledged. Cooldown started."}), 200

    return jsonify({"error": "Patient not found"}), 404







@app.route('/')
def dashboard():
    return render_template("index.html")

# API Endpoints for simulation control 

@app.route('/api/status')
def simulation_status():
    return jsonify({
        "running": simulation_running,
        "patients": [pid for pid in patients.keys()],
        "data_size": os.path.getsize(CSV_FILE) if os.path.exists(CSV_FILE) else 0
    }), 200

@app.route('/api/start', methods=['POST'])
def start_simulation():
    global simulation_running
    simulation_running = True
    return jsonify({"status": "Simulation started"}), 200

@app.route('/api/stop', methods=['POST'])
def stop_simulation():
    global simulation_running
    simulation_running = False
    return jsonify({"status": "Simulation stopped"}), 200

@app.route('/api/restart', methods=['POST'])
def restart_simulation():
    global simulation_running, patients
    
    with patients_lock:
        # Reset all patients and thresholds
        patients = {f"P{i+1}": Patient(f"P{i+1}") for i in range(5)}
        
        # Clear data files
        if os.path.exists(CSV_FILE):
            os.remove(CSV_FILE)
        if os.path.exists(ALERT_LOG_CSV):
            os.remove(ALERT_LOG_CSV)
            
    simulation_running = True
    return jsonify({
        "status": "Simulation restarted",
        "new_patients": list(patients.keys())
    }), 200


@app.route('/api/patient_history/<pid>')
def patient_history(pid):
    with patients_lock:
        if pid in patients:
            patient = patients[pid]
            
            return jsonify({
                "history": patient.history, 
                "heartrate_history": patient.heartrate_history
            })
        else:
            return jsonify({"error": "Patient not found"}), 404



# Run the Flask web server with Socket.IO
if __name__ == '__main__':
    threading.Thread(target=simulation_thread, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
