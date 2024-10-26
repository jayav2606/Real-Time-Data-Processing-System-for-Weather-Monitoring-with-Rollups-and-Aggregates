from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import threading
import json
import sqlite3
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import logging
import signal
import sys
import time

# Set up logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
CORS(app)

# Load configuration from config.json
with open('config.json') as config_file:
    config = json.load(config_file)

API_KEY = config["api_key"]
INTERVAL = config["interval_minutes"]
TEMP_UNIT = config["temp_unit"]
ALERT_THRESHOLD = config["alert_threshold"]["temperature"]
EMAIL_CONFIG = config.get("email", {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "username": "your-email@gmail.com",
    "password": "your-app-password",
    "recipients": ["recipient@example.com"]
})

cities = ["Delhi", "Mumbai", "Chennai", "Bangalore", "Kolkata", "Hyderabad"]

shutdown_flag = threading.Event()
scheduler_started = False

def init_db():
    """Initialize database with correct schema"""
    conn = sqlite3.connect('weather.db', detect_types=sqlite3.PARSE_DECLTYPES)
    cursor = conn.cursor()
    
    # Drop existing tables to ensure correct schema
    cursor.execute('DROP TABLE IF EXISTS weather')
    cursor.execute('DROP TABLE IF EXISTS alerts')
    cursor.execute('DROP TABLE IF EXISTS forecasts')
    
    # Create tables with correct schema
    cursor.execute('''CREATE TABLE weather (
                        id INTEGER PRIMARY KEY,
                        city TEXT NOT NULL,
                        date DATE NOT NULL,
                        avg_temp REAL,
                        max_temp REAL,
                        min_temp REAL,
                        dominant_condition TEXT,
                        avg_humidity REAL,
                        avg_wind_speed REAL,
                        avg_pressure REAL,
                        avg_feels_like REAL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    cursor.execute('''CREATE TABLE alerts (
                        id INTEGER PRIMARY KEY,
                        city TEXT NOT NULL,
                        alert_type TEXT,
                        message TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        acknowledged BOOLEAN DEFAULT FALSE)''')
    
    cursor.execute('''CREATE TABLE forecasts (
                        id INTEGER PRIMARY KEY,
                        city TEXT NOT NULL,
                        forecast_date DATE,
                        temperature REAL,
                        condition TEXT,
                        probability REAL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    conn.close()

def convert_temperature(temp, from_unit='C', to_unit='C'):
    if from_unit == to_unit:
        return temp
    if from_unit == 'C' and to_unit == 'F':
        return (temp * 9/5) + 32
    if from_unit == 'F' and to_unit == 'C':
        return (temp - 32) * 5/9

def send_alert_email(subject, message):
    try:
        msg = MIMEText(message)
        msg['Subject'] = subject
        msg['From'] = EMAIL_CONFIG['username']
        msg['To'] = ', '.join(EMAIL_CONFIG['recipients'])

        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.starttls()
        server.login(EMAIL_CONFIG['username'], EMAIL_CONFIG['password'])
        server.send_message(msg)
        server.quit()
        logging.info(f"Alert email sent: {subject}")
    except Exception as e:
        logging.error(f"Failed to send alert email: {str(e)}")

def store_alert(city, alert_type, message):
    try:
        conn = sqlite3.connect('weather.db')
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO alerts (city, alert_type, message) 
                         VALUES (?, ?, ?)''', (city, alert_type, message))
        conn.commit()
    except Exception as e:
        logging.error(f"Failed to store alert: {str(e)}")
    finally:
        conn.close()

def get_weather(city):
    current_url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"
    forecast_url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={API_KEY}&units=metric"
    
    try:
        current_response = requests.get(current_url)
        forecast_response = requests.get(forecast_url)
        
        if current_response.status_code == 200 and forecast_response.status_code == 200:
            current_data = current_response.json()
            forecast_data = forecast_response.json()
            
            weather_data = {
                "temperature": current_data["main"]["temp"],
                "feels_like": current_data["main"]["feels_like"],
                "condition": current_data["weather"][0]["main"],
                "humidity": current_data["main"]["humidity"],
                "wind_speed": current_data["wind"]["speed"],
                "pressure": current_data["main"]["pressure"],
                "forecast": []
            }
            
            for item in forecast_data["list"][:5]:
                weather_data["forecast"].append({
                    "date": datetime.fromtimestamp(item["dt"]).date(),
                    "temperature": item["main"]["temp"],
                    "condition": item["weather"][0]["main"],
                    "probability": item.get("pop", 0) * 100
                })
            
            return weather_data
    except Exception as e:
        logging.error(f"Error fetching weather data for {city}: {str(e)}")
    return None

def check_alerts(weather_data, city):
    if weather_data["temperature"] > ALERT_THRESHOLD:
        message = f"High temperature alert for {city}: {weather_data['temperature']}°C"
        store_alert(city, "temperature", message)
        send_alert_email(f"Weather Alert - {city}", message)

def store_forecast(city, forecasts):
    try:
        conn = sqlite3.connect('weather.db')
        cursor = conn.cursor()
        
        for forecast in forecasts:
            cursor.execute('''INSERT INTO forecasts (city, forecast_date, temperature, condition, probability)
                            VALUES (?, ?, ?, ?, ?)''',
                         (city, forecast["date"], forecast["temperature"], 
                          forecast["condition"], forecast["probability"]))
        
        conn.commit()
    except Exception as e:
        logging.error(f"Failed to store forecast: {str(e)}")
    finally:
        conn.close()

def store_daily_summary(city, avg_temp, max_temp, min_temp, dominant_condition,
                       avg_humidity, avg_wind_speed, avg_pressure, avg_feels_like):
    try:
        conn = sqlite3.connect('weather.db')
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO weather (
                            city, date, avg_temp, max_temp, min_temp, 
                            dominant_condition, avg_humidity, avg_wind_speed, 
                            avg_pressure, avg_feels_like) 
                         VALUES (?, DATE('now'), ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (city, avg_temp, max_temp, min_temp, dominant_condition,
                       avg_humidity, avg_wind_speed, avg_pressure, avg_feels_like))
        conn.commit()
    except Exception as e:
        logging.error(f"Failed to store daily summary: {str(e)}")
    finally:
        conn.close()

def fetch_and_store():
    daily_data = {city: [] for city in cities}
    
    for city in cities:
        weather_data = get_weather(city)
        if weather_data:
            # Store the current temperature reading
            daily_data[city].append(weather_data)
            check_alerts(weather_data, city)
            store_forecast(city, weather_data["forecast"])
            logging.info(f"Fetched data for {city}: {weather_data}")

    for city, data in daily_data.items():
        if data:
            # Calculate basic averages
            avg_temp = sum(d["temperature"] for d in data) / len(data)
            avg_humidity = sum(d["humidity"] for d in data) / len(data)
            avg_wind = sum(d["wind_speed"] for d in data) / len(data)
            avg_pressure = sum(d["pressure"] for d in data) / len(data)
            avg_feels_like = sum(d["feels_like"] for d in data) / len(data)
            
            # Get min and max temperatures from forecast data
            try:
                conn = sqlite3.connect('weather.db')
                cursor = conn.cursor()
                
                # Get today's date in the format stored in the database
                today = datetime.now().date()
                
                # Fetch all temperatures for this city and date from forecasts
                cursor.execute('''
                    SELECT temperature 
                    FROM forecasts 
                    WHERE city = ? AND date(forecast_date) = date(?)
                ''', (city, today))
                
                temperatures = [row[0] for row in cursor.fetchall()]
                
                if temperatures:
                    max_temp = max(temperatures)
                    min_temp = min(temperatures)
                else:
                    # Fallback to current temperature if no forecast data
                    max_temp = data[0]["temperature"]
                    min_temp = data[0]["temperature"]
                
            except Exception as e:
                logging.error(f"Error fetching min/max temps for {city}: {str(e)}")
                # Fallback values
                max_temp = data[0]["temperature"]
                min_temp = data[0]["temperature"]
            finally:
                conn.close()

            dominant_condition = max(set(d["condition"] for d in data), 
                                  key=lambda x: len([d for d in data if d["condition"] == x]))

            store_daily_summary(
                city, avg_temp, max_temp, min_temp, dominant_condition,
                avg_humidity, avg_wind, avg_pressure, avg_feels_like
            )



@app.route('/')
def home():
    return "Welcome to the Weather API. Available endpoints: /api/weather, /api/alerts, /api/forecast"

@app.route('/api/weather', methods=['GET'])
def get_weather_summary():
    try:
        unit = request.args.get('unit', TEMP_UNIT)
        days = request.args.get('days', 7, type=int)
        
        conn = sqlite3.connect('weather.db')
        cursor = conn.cursor()
        
        cursor.execute('''SELECT * FROM weather 
                         WHERE date >= date('now', ?) 
                         ORDER BY date DESC''', (f'-{days} days',))
        results = cursor.fetchall()
        
        summary = []
        for row in results:
            summary.append({
                "city": row[1],
                "date": row[2],
                "avg_temp": convert_temperature(row[3], 'C', unit),
                "max_temp": convert_temperature(row[4], 'C', unit),
                "min_temp": convert_temperature(row[5], 'C', unit),
                "dominant_condition": row[6],
                "avg_humidity": row[7],
                "avg_wind_speed": row[8],
                "avg_pressure": row[9],
                "avg_feels_like": row[10]
            })
        
        return jsonify(summary)
    except Exception as e:
        logging.error(f"Error in get_weather_summary: {str(e)}")
        return jsonify({"error": "Failed to fetch weather data"}), 500
    finally:
        conn.close()

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    try:
        conn = sqlite3.connect('weather.db')
        cursor = conn.cursor()
        
        cursor.execute('''SELECT * FROM alerts 
                         WHERE acknowledged = FALSE 
                         ORDER BY timestamp DESC''')
        results = cursor.fetchall()
        
        alerts = []
        for row in results:
            alerts.append({
                "city": row[1],
                "alert_type": row[2],
                "message": row[3],
                "timestamp": row[4],
                "acknowledged": bool(row[5])
            })
        
        return jsonify(alerts)
    except Exception as e:
        logging.error(f"Error in get_alerts: {str(e)}")
        return jsonify({"error": "Failed to fetch alerts"}), 500
    finally:
        conn.close()

@app.route('/api/forecast', methods=['GET'])
def get_forecast():
    try:
        conn = sqlite3.connect('weather.db')
        cursor = conn.cursor()
        
        cursor.execute('''SELECT * FROM forecasts 
                         WHERE forecast_date >= DATE('now')
                         ORDER BY forecast_date ASC''')
        results = cursor.fetchall()
        
        forecasts = []
        for row in results:
            forecasts.append({
                "city": row[1],
                "forecast_date": row[2],
                "temperature": row[3],
                "condition": row[4],
                "probability": row[5],
                "timestamp": row[6]
            })
        
        return jsonify(forecasts)
    except Exception as e:
        logging.error(f"Error in get_forecast: {str(e)}")
        return jsonify({"error": "Failed to fetch forecast data"}), 500
    finally:
        conn.close()

def scheduler():
    while not shutdown_flag.is_set():
        try:
            fetch_and_store()
        except Exception as e:
            logging.error(f"Error in scheduler: {str(e)}")
        time.sleep(INTERVAL * 60)

@app.before_request
def start_scheduler_once():
    global scheduler_started
    if not scheduler_started:
        thread = threading.Thread(target=scheduler)
        thread.daemon = True
        thread.start()
        scheduler_started = True

def signal_handler(sig, frame):
    logging.info("Shutting down gracefully...")
    shutdown_flag.set()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

if __name__ == '__main__':
    try:
        init_db()
        app.run(debug=True, host="127.0.0.1", port=5005)
    except Exception as e:
        logging.error(f"Failed to start application: {str(e)}")
        sys.exit(1)



