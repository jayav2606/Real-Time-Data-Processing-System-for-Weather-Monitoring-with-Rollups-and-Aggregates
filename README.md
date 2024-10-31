# Real-Time-Data-Processing-System-for-Weather-Monitoring-with-Rollups-and-Aggregates
A weather monitoring system built using Flask, SQLite, and OpenWeather API. This application retrieves weather data for multiple cities, stores it in a database, and issues alerts based on configurable thresholds. It also provides a REST API to access current weather summaries, alerts, and forecasts.

## Features
- Retrieve and store real-time and forecasted weather data for configured cities
- Issue email alerts for high-temperature thresholds
- SQLite database storage for daily summaries, alerts, and forecasts
- REST API endpoints for weather summaries, alerts, and forecasts
- Background scheduler to fetch weather data at regular intervals
- Configurable options for email, temperature units, and API key

## Requirements
- Python 3.x
- Flask
- Flask-CORS
- SQLite
- OpenWeather API Key
- Email server credentials (for alerting)   (optional)

## Setup

1. **Clone the repository:**
     ```bash
     git clone https://github.com/jayav/Real-Time-Data-Processing-System-for-Weather-Monitoring-with-Rollups-and-Aggregates.git
     cd Real-Time-Data-Processing-System-for-Weather-Monitoring-with-Rollups-and-Aggregates
2. **Create a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows, use venv\Scripts\activate
3. **Install Dependencies:**
    ```bash
     pip install -r requirements.txt
**if this does not install all the dependencies, check the requirements.txt file and install the dependencies listed in there manually using pip install.**
## Configuration
 **The config.json file includes:**
   - api_key: OpenWeather API key
   - interval_minutes: Interval in minutes to fetch weather data
   - temp_unit: Temperature unit (C for Celsius, F for Fahrenheit)
   - alert_threshold: Temperature threshold for sending alerts
   - email: Configuration for the email server (SMTP)
## Running the Application
1. **Start the application:**
    ```bash
     python app.py
**The app runs on http://127.0.0.1:5005 by default.If you run this on any other port, change the port in index.html file too.**
### Open index.html file directly or run index.html (If you plan to open html file using IDE)  -----   -------   (index.html <<------This is the Main Frontend) ###


   
           



![Screenshot (690)](https://github.com/user-attachments/assets/6b8ab11f-7ec5-4499-9bf5-cdbe01c8ca64)



    
    



