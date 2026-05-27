import psycopg2
import requests
import logging
import time
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
        
        cur.execute("SELECT id, created_at FROM feedback_ratings WHERE temperature IS NULL;")
        missing_rows = cur.fetchall()
        
        if not missing_rows:
            logging.info("No missing weather data found. Database is up to date!")
            cur.close()
            conn.close()
            return
            
        # STEP 1: Group the missing rows by Date
        date_groups = {}
        for row in missing_rows:
            row_id = row[0]
            created_at = row[1] 
            
            date_str = created_at.strftime("%Y-%m-%d")
            hour = created_at.hour
            
            if date_str not in date_groups:
                date_groups[date_str] = []
                
            date_groups[date_str].append({'id': row_id, 'hour': hour})
            
        logging.info(f"Found {len(missing_rows)} missing rows spread across {len(date_groups)} different days.")

        # STEP 2: Fetch the historical weather for each unique day
        for date_str, rows in date_groups.items():
            logging.info(f"Fetching 24-hour weather archive for {date_str}...")
            
            # --- FIXED URL: Using the Archive API instead of Forecast ---
            weather_url = (
                f"https://archive-api.open-meteo.com/v1/archive?latitude=-36.85&longitude=174.76"
                f"&start_date={date_str}&end_date={date_str}"
                f"&hourly=temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,relative_humidity_2m"
                f"&timezone=Pacific%2FAuckland"
            )
            
            max_retries = 3
            weather_data = None
            
            for attempt in range(max_retries):
                try:
                    response = requests.get(weather_url, timeout=30)
                    response.raise_for_status() 
                    weather_data = response.json()
                    break 
                    
                except Exception as api_err:
                    if attempt < max_retries - 1:
                        logging.warning(f"API timeout for {date_str}. Retrying in 5 seconds... (Attempt {attempt + 1} of {max_retries})")
                        time.sleep(5) 
                    else:
                        logging.error(f"API failed for {date_str} after {max_retries} attempts. Skipping this day.")
            
            if not weather_data or 'hourly' not in weather_data:
                continue
                
            hourly_data = weather_data['hourly']
            
            # STEP 3: Match the exact hour to the database row
            for r in rows:
                row_id = r['id']
                hr = r['hour'] 
                
                temp = hourly_data['temperature_2m'][hr]
                
                # --- NEW SAFETY CHECK: Don't write NULLs to the database ---
                if temp is None:
                    logging.warning(f"API returned null data for {date_str} at hour {hr}. Skipping DB update.")
                    continue
                    
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
            
            # Save progress instantly after each successful day
            conn.commit()
            
            # Polite delay between successful daily calls
            time.sleep(2)
                
        logging.info("Batch job fully complete!")

    except Exception as e:
        logging.error(f"Batch job failed due to an error: {e}")
        raise e
        
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    update_missing_weather_historically()
