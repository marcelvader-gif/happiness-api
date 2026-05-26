import psycopg2
import requests
import logging
from datetime import datetime

# --- Set Up Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Database Configuration ---
DB_HOST = "ep-lively-breeze-aqxoqdds-pooler.c-8.us-east-1.aws.neon.tech"  
DB_NAME = "neondb"                                                    
DB_USER = "neondb_owner"                                              
DB_PASS = "npg_Exf9wJS2ZNRD"                                        
DB_PORT = "5432"

def update_missing_weather_historically():
    logging.info("Starting historical weather batch job...")
    
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, 
            password=DB_PASS, port=DB_PORT, sslmode='require'
        )
        cur = conn.cursor()
        
        # We grab BOTH the ID and the timestamp this time
        cur.execute("SELECT id, created_at FROM feedback_ratings WHERE temperature IS NULL;")
        missing_rows = cur.fetchall()
        
        if not missing_rows:
            logging.info("No missing weather data found. Database is up to date!")
            cur.close()
            conn.close()
            return
            
        # STEP 1: Group the missing rows by Date to prevent spamming the API
        date_groups = {}
        for row in missing_rows:
            row_id = row[0]
            created_at = row[1] # This is a Python datetime object from Postgres
            
            # Extract the date string (YYYY-MM-DD) and the exact hour (0-23)
            date_str = created_at.strftime("%Y-%m-%d")
            hour = created_at.hour
            
            if date_str not in date_groups:
                date_groups[date_str] = []
                
            date_groups[date_str].append({'id': row_id, 'hour': hour})
            
        logging.info(f"Found {len(missing_rows)} missing rows spread across {len(date_groups)} different days.")

        # STEP 2: Fetch the historical weather for each unique day
        for date_str, rows in date_groups.items():
            logging.info(f"Fetching 24-hour weather history for {date_str}...")
            
            # Open-Meteo's API allows searching past dates by specifying start_date and end_date
            weather_url = (
                f"https://api.open-meteo.com/v1/forecast?latitude=-36.85&longitude=174.76"
                f"&start_date={date_str}&end_date={date_str}"
                f"&hourly=temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,relative_humidity_2m"
                f"&timezone=Pacific%2FAuckland"
            )
            
            response = requests.get(weather_url, timeout=10)
            weather_data = response.json()
            
            if 'hourly' not in weather_data:
                logging.error(f"API failed to return hourly data for {date_str}. Skipping these rows.")
                continue
                
            hourly_data = weather_data['hourly']
            
            # STEP 3: Match the exact hour to the database row
            for r in rows:
                row_id = r['id']
                hr = r['hour'] # e.g., if it happened at 14:30, the hour is 14
                
                # The API returns an array of 24 items (one for each hour). We use the hour as the array index!
                temp = hourly_data['temperature_2m'][hr]
                app_temp = hourly_data['apparent_temperature'][hr]
                precip = hourly_data['precipitation'][hr]
                w_code = hourly_data['weather_code'][hr]
                wind = hourly_data['wind_speed_10m'][hr]
                humidity = hourly_data['relative_humidity_2m'][hr]
                
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
        logging.info("Successfully patched all historical weather data!")

    except Exception as e:
        logging.error(f"Batch job failed due to an error: {e}")
        raise e
        
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    update_missing_weather_historically()
