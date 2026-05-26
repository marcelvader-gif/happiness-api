import psycopg2
import requests
import logging

# --- Set Up Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Database Configuration ---
DB_HOST = "ep-lively-breeze-aqxoqdds-pooler.c-8.us-east-1.aws.neon.tech"  
DB_NAME = "neondb"                                                    
DB_USER = "neondb_owner"                                              
DB_PASS = "npg_Exf9wJS2ZNRD"                                        
DB_PORT = "5432"

def update_missing_weather():
    logging.info("Starting nightly weather batch job...")
    
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, 
            password=DB_PASS, port=DB_PORT, sslmode='require'
        )
        cur = conn.cursor()
        
        # Find rows missing weather data
        cur.execute("SELECT id FROM feedback_ratings WHERE temperature IS NULL;")
        missing_rows = cur.fetchall()
        
        if not missing_rows:
            logging.info("No missing weather data found. Database is up to date!")
            cur.close()
            conn.close()
            return
            
        logging.info(f"Found {len(missing_rows)} rows missing weather data. Processing...")

        # FIX 1: Request ALL 6 weather variables from the API
        weather_url = "https://api.open-meteo.com/v1/forecast?latitude=-36.85&longitude=174.76&current=temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,relative_humidity_2m"
        response = requests.get(weather_url, timeout=5)
        weather_data = response.json()
        
        current_data = weather_data.get('current', {})
        
        # Extract all variables
        temp = current_data.get('temperature_2m')
        app_temp = current_data.get('apparent_temperature')
        precip = current_data.get('precipitation')
        w_code = current_data.get('weather_code')
        wind = current_data.get('wind_speed_10m')
        humidity = current_data.get('relative_humidity_2m')
        
        logging.info(f"Fetched current weather fallback: Temp {temp}°C, Weather Code {w_code}")

        # FIX 1 (Continued): Update ALL separate columns in the database loop
        for row in missing_rows:
            row_id = row[0]
            cur.execute(
                """UPDATE feedback_ratings 
                   SET temperature = %s, 
                       apparent_temperature = %s, 
                       precipitation = %s, 
                       weather_code = %s, 
                       wind_speed = %s, 
                       humidity = %s 
                   WHERE id = %s""",
                (temp, app_temp, precip, w_code, wind, humidity, row_id)
            )
            
        conn.commit()
        logging.info(f"Successfully backfilled {len(missing_rows)} rows with complete weather data.")

    except Exception as e:
        logging.error(f"Batch job failed due to an error: {e}")
        raise e
        
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    update_missing_weather()
