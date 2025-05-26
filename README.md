Real-Time Health Monitoring Prototype
This repository contains the source code for a real-time health monitoring prototype developed as part of the final year dissertation project for the 6001CEM Individual Project module at Coventry University.

The system simulates patient vital signs (SpO₂ and heart rate), uses machine learning to detect anomalies, and triggers real-time alerts through a browser-based dashboard.

Project Title
Developing a Web Application Prototype for Real-Time Health Monitoring in Remote Settings Using Simulated Data and Machine Learning-Driven Alerts for Early Intervention

Author
Jatin Gera
Final Year BSc Computer Science
Coventry University
Supervisor: Dr. Katerina Stamou

Overview
This system demonstrates the feasibility of using machine learning in remote health monitoring. It uses synthetic data, an Isolation Forest anomaly detection model, and real-time updates through a Flask-SocketIO backend.

Key Features:
Synthetic simulation of SpO₂ and heart rate using sine waves and Gaussian noise
Rolling buffer to maintain recent readings
Isolation Forest for unsupervised anomaly detection
Adaptive thresholds based on percentile calculations
Real-time alert system with cooldown recovery mechanism
Socket.IO streaming for dashboard interactivity
Lightweight HTML/CSS/JS frontend
Technologies Used
Backend: Python, Flask, Flask-SocketIO
Machine Learning: Scikit-learn
Simulation & Data: NumPy, CSV
Frontend: HTML, CSS, JavaScript
Data Exchange: JSON
Repository Structure
project-root/ │ ├── app.py # Main Flask application with backend routes ├── ml_model.py # Isolation Forest logic and adaptive thresholding ├── simulate.py # Simulated sensor data generation (SpO₂, HR) ├── static/ │ └── style.css # Stylesheet for the dashboard ├── templates/ │ └── index.html # Main dashboard page ├── data/ │ └── alert_log.csv # Log of triggered alerts └── requirements.txt # Python dependencies

How to Run the Project
1. Clone the repository
git clone https://github.com/yourusername/health-monitoring-prototype.git cd health-monitoring-prototype

2. Create a virtual environment (recommended)
python -m venv venv source venv/bin/activate # On Windows: venv\Scripts\activate

3. Install dependencies
pip install -r requirements.txt

4. Run the application
python app.py

5. View the dashboard
Open a browser and navigate to: http://localhost:5000

You will see a live dashboard showing vitals, alert status, and real-time updates.

Notes
The system simulates 5 patients with second-wise SpO₂ and HR updates.

Alerts are logged in data/alert_log.csv for analysis.

Isolation Forest is retrained on a rolling buffer of the last 50 readings per patient.

The “Acknowledge Alert” button activates a cooldown to reduce alert fatigue.

User testing feedback was collected via a Google Form (see dissertation Section 7.3).

Disclaimer
This is an academic prototype using simulated data. It is not designed or validated for clinical use.

License
This repository is provided for educational and review purposes only. No commercial use is permitted.
