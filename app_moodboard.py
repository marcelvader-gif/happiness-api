from flask import Flask, request, jsonify
import psycopg2
import requests 
import os

app = Flask(__name__)

# --- Database Configuration ---
DB_HOST = "ep-lively-breeze-aqxoqdds-pooler.c-8.us-east-1.aws.neon.tech"  
DB_NAME = "neondb"                                                    
DB_USER = "neondb_owner"                                              
DB_PASS = "npg_Exf9wJS2ZNRD"                                        
DB_PORT = "5432"

def get_db_connection():
    """Establishes and returns a connection to the PostgreSQL database."""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT,      
        sslmode='require'  
    )
    return conn

@app.route('/api/rating', methods=['POST'])
def receive_rating():
    print("\n========== INCOMING REQUEST DETECTED ==========")
    
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    q_id = data.get('question_id')
    score = data.get('rating_score')
    print(f"Parsed Content -> Question ID: {q_id} | Rating Score: {score}")

    # --- Fetch Advanced Auckland Weather from Open-Meteo ---
    print("Fetching advanced live weather for Auckland...")
    
    # Initialize variables as None in case the API fails
    temp = app_temp = precip = w_code = wind = humidity = None
    
    try:
        # We ask for all 6 variables in this single URL
        weather_url = "https://api.open-meteo.com/v1/forecast?latitude=-36.85&longitude=174.76&current=temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,relative_humidity_2m"
        response = requests.get(weather_url, timeout=5)
        weather_data = response.json()
        
        current_data = weather_data.get('current', {})
        
        # Extract each specific piece of data
        temp = current_data.get('temperature_2m')
        app_temp = current_data.get('apparent_temperature')
        precip = current_data.get('precipitation')
        w_code = current_data.get('weather_code')
        wind = current_data.get('wind_speed_10m')
        humidity = current_data.get('relative_humidity_2m')
        
        print(f"Weather fetched! Temp: {temp}°C, Precip: {precip}mm, Wind: {wind}km/h")
    except Exception as e:
        print(f"Weather API failed (will save rating with empty weather columns): {e}")

    # --- Database Insertion ---
    try:
        print("Attempting connection to PostgreSQL database...")
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Inject all the separated variables into their own columns
        cur.execute(
            """INSERT INTO feedback_ratings 
               (question_id, rating_score, temperature, apparent_temperature, precipitation, weather_code, wind_speed, humidity) 
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (q_id, score, temp, app_temp, precip, w_code, wind, humidity)
        )
        conn.commit()
        cur.close()
        conn.close()
        print("DATABASE SUCCESS! Row and full weather data added to PostgreSQL.")
        
        # Send the data back to the ESP32
        return jsonify({
            "status": "success", 
            "message": "Saved to database",
            "temperature": temp,
            "weather_code": w_code
        }), 201

    except Exception as e:
        print(f"DATABASE ERROR: {e}")
        return jsonify({"status": "network_test_success", "db_error": str(e), "temperature": temp}), 201

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
