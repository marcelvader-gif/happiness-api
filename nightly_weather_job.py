import psycopg2
import requests
import logging
from datetime import datetime

# --- 1. Set Up Professional Logging ---
# This ensures logs show timestamps and clearly state if it's an INFO, WARNING, or ERROR
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- 2. Database Configuration ---
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
        
        # Find rows that missed the weather check
        cur.execute("SELECT id FROM feedback_ratings WHERE temperature IS NULL;")
        missing_rows = cur.fetchall()
        
        if not missing_rows:
            logging.info("No missing weather data found. Database is up to date!")
            cur.close()
            conn.close()
            return
            
        logging.info(f"Found {len(missing_rows)} rows missing weather data. Processing...")

        # Fetch the current weather (For a true historical backfill, you'd parse the date 
        # and use Open-Meteo's historical API, but we'll use current for this teaching demo)
        weather_url = "https://api.open-meteo.com/v1/forecast?latitude=-36.85&longitude=174.76&current=temperature_2m,weather_code"
        response = requests.get(weather_url, timeout=5)
        weather_data = response.json()
        
        temp = weather_data['current']['temperature_2m']
        w_code = weather_data['current']['weather_code']
        logging.info(f"Fetched weather fallback: Temp {temp}°C, Code {w_code}")

        # Update the missing rows
        for row in missing_rows:
            row_id = row[0]
            cur.execute(
                "UPDATE feedback_ratings SET temperature = %s, weather_code = %s WHERE id = %s",
                (temp, w_code, row_id)
            )
            logging.info(f"Updated row ID {row_id} with weather data.")
            
        conn.commit()
        logging.info("Batch job completed successfully. Changes saved to database.")

    except Exception as e:
        logging.error(f"Batch job failed due to an error: {e}")
        raise e # <--- THIS WILL FORCE GITHUB TO TURN RED IF IT FAILS!
        
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    update_missing_weather()
