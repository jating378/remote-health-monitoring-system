import time
import random
import json
import csv

# Define SpO2, Heart Rate, and Blood Pressure ranges
VITAL_RANGES = {
    "spo2": {
        "normal": (95, 100),
        "warning": (90, 94.9),
        "critical": (70, 89.9)
    },
    "heart_rate": {
        "normal": (60, 100),
        "warning": (50, 59.9),  # Low warning 
        "critical": (30, 49.9),  # Extremely low HR
        "high_warning": (100.1, 110),  # High warning HR
        "high_critical": (110.1, 150)  # Extremely high HR
    },
    "blood_pressure": {
        "normal_systolic": (90, 120),
        "normal_diastolic": (60, 80),
        "warning_systolic": (120, 140),
        "warning_diastolic": (80, 90),
        "critical_systolic": (0, 80),  # Critical if systolic <= 80 or systolic >= 140
        "critical_diastolic": (0, 50),  # Critical if diastolic <= 50 or diastolic >= 90
    }
}

# Number of patients
NUM_PATIENTS = 5  # Change this if testing multiple patients

# Assign initial states for all patients
patients = []
for i in range(NUM_PATIENTS):
    patient = {
        "id": i + 1,
        "current_spo2": random.uniform(*VITAL_RANGES["spo2"]["normal"]),
        "current_hr": random.randint(*VITAL_RANGES["heart_rate"]["normal"]),
        "current_systolic_bp": random.randint(*VITAL_RANGES["blood_pressure"]["normal_systolic"]),
        "current_diastolic_bp": random.randint(*VITAL_RANGES["blood_pressure"]["normal_diastolic"]),
        "is_spo2_decreasing": False,
        "is_hr_changing": False,  
        "spo2_hold_counter": 0,
        "hr_hold_counter": 0,
        "bp_hold_counter": 0,
        "alert_triggered": False,  # Tracks if an alert has been triggered
        "alert_confirm_counter": 3,  # Allow some delay before final alert lock
    }
    patients.append(patient)

# Define decrease probability
decrease_probability = 0.02

def simulate_vitals(patient):
    """
    Simulate SpO2, Heart Rate (HR), and Blood Pressure (BP) with realistic interdependencies.
    """
    if patient["alert_triggered"]:
        # If alert is triggered, retain last values
        return patient

    alert_triggered = False  

    # === Simulate SpO2 ===
    current_spo2 = patient["current_spo2"]
    is_spo2_decreasing = patient["is_spo2_decreasing"]
    spo2_hold_counter = patient["spo2_hold_counter"]

    if not is_spo2_decreasing:
        normal_fluctuation = random.uniform(-0.2, 0.2)  
        next_spo2 = current_spo2 + normal_fluctuation
        next_spo2 = max(min(next_spo2, VITAL_RANGES["spo2"]["normal"][1]), VITAL_RANGES["spo2"]["normal"][0])  

        if random.random() < decrease_probability:  
            is_spo2_decreasing = True  
            spo2_hold_counter = random.randint(2, 10)  
    else:
        if spo2_hold_counter > 0:
            next_spo2 = current_spo2  
            spo2_hold_counter -= 1  
        else:
            decrement = random.uniform(0.1, 0.5)  
            next_spo2 = current_spo2 - decrement
            spo2_hold_counter = random.randint(2, 10)  

        

    # === Simulate Heart Rate (HR) ===
    current_hr = patient["current_hr"]
    is_hr_changing = patient["is_hr_changing"]
    hr_hold_counter = patient["hr_hold_counter"]

    if hr_hold_counter > 0:  
        next_hr = current_hr
        hr_hold_counter -= 1  
    else:
        if is_spo2_decreasing:
            hr_increase = random.randint(2, 7)  
            next_hr = current_hr + hr_increase  
        else:
            hr_fluctuation = random.randint(-2, 2)  
            next_hr = current_hr + hr_fluctuation  

        if random.random() < 0.02:  
            is_hr_changing = not is_hr_changing  

        if is_hr_changing:
            hr_decrement = random.randint(2, 7)
            next_hr = current_hr - hr_decrement

        hr_hold_counter = random.randint(2, 10)  

        

    next_hr = max(min(next_hr, VITAL_RANGES["heart_rate"]["high_critical"][1]), VITAL_RANGES["heart_rate"]["normal"][0])  





    # === Simulate Blood Pressure (BP) ===
    current_systolic_bp = patient["current_systolic_bp"]
    current_diastolic_bp = patient["current_diastolic_bp"]
    bp_hold_counter = patient["bp_hold_counter"]

    if bp_hold_counter > 0:
        next_systolic_bp = current_systolic_bp
        next_diastolic_bp = current_diastolic_bp
        bp_hold_counter -= 1
    else:
        # BP tends to rise when heart rate increases
        if current_hr > 120:
            systolic_increase = random.randint(2, 7)
            diastolic_increase = random.randint(1,3 )
            next_systolic_bp = current_systolic_bp + systolic_increase
            next_diastolic_bp = current_diastolic_bp + diastolic_increase
        elif current_hr < 50:
            systolic_decrease = random.randint(2, 7)
            diastolic_decrease = random.randint(2, 7)
            next_systolic_bp = current_systolic_bp - systolic_decrease
            next_diastolic_bp = current_diastolic_bp - diastolic_decrease
        else:
            # Normal fluctuations in BP
            systolic_fluctuation = random.randint(-3, 3)
            diastolic_fluctuation = random.randint(-2, 2)
            next_systolic_bp = current_systolic_bp + systolic_fluctuation
            next_diastolic_bp = current_diastolic_bp + diastolic_fluctuation

        bp_hold_counter = random.randint(1, 3)

    

    # === Alert Triggering ===
   
    if patient["current_systolic_bp"] >= 140 or patient["current_diastolic_bp"] >= 90:
        alert_triggered = True


    if next_spo2 <= 90 or next_hr <=  50 or \
       next_hr >= 140 :
       alert_triggered = True  

    patient["current_spo2"] = round(next_spo2, 1)
    patient["current_hr"] = round(next_hr, 1)
    patient["current_systolic_bp"] = round(next_systolic_bp, 1)
    patient["current_diastolic_bp"] = round(next_diastolic_bp, 1)
    patient["is_spo2_decreasing"] = is_spo2_decreasing
    patient["spo2_hold_counter"] = spo2_hold_counter
    patient["is_hr_changing"] = is_hr_changing
    patient["hr_hold_counter"] = hr_hold_counter
    patient["bp_hold_counter"] = bp_hold_counter

    if alert_triggered:
        patient["alert_triggered"] = True

    return patient


if __name__ == "__main__":
    print(f"Monitoring {NUM_PATIENTS} Patients...\n")

    while any(not patient["alert_triggered"] for patient in patients):
        for patient in patients:
            if not patient["alert_triggered"]:
                patient = simulate_vitals(patient)


            # SpO2 and Heart Rate
            spo2_status = "Critical" if patient["current_spo2"] <= 90 else \
            "Warning" if 90 <= patient["current_spo2"] < 95 else "Normal"


            hr_status = "Critical" if patient["current_hr"] <= 50 or patient["current_hr"] >= 140 else \
            "Warning" if 50 < patient["current_hr"] < 60 or 120 < patient["current_hr"] < 140 else "Normal"


            # BP status 
            if patient["current_systolic_bp"] >= 140 or patient["current_diastolic_bp"] >= 90:
                bp_status = "Critical"
            elif 130 <= patient["current_systolic_bp"] < 140 or 80 <= patient["current_diastolic_bp"] < 90:
                bp_status = "Warning"
            else:
                bp_status = "Normal"



            print(f"Patient {patient['id']} - SpO2: {patient['current_spo2']}% ({spo2_status}), HR: {patient['current_hr']} bpm ({hr_status}), BP: {patient['current_systolic_bp']}/{patient['current_diastolic_bp']} mmHg ({bp_status})\n")
        
        # Wait for a moment before next iteration
        time.sleep(1)

    print("\nAlert triggered for one or more patients!")
