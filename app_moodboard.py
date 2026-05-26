from flask import Flask, request, jsonify
import psycopg2
import os

app = Flask(__name__)

# --- Database Configuration ---
DB_HOST = "ep-lively-breeze-aqxoqdds-pooler.c-8.us-east-1.aws.neon.tech"  # The middle part of your Neon link
DB_NAME = "neondb"                                    # Usually neondb
DB_USER = "neondb_owner"                              # Usually neondb_owner
DB_PASS = "npg_Exf9wJS2ZNRD"                        # The password you saved to Notepad
DB_PORT = "5432"

def get_db_connection():
    """Establishes and returns a connection to the PostgreSQL database."""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT,      # <--- ADD THIS COMMA RIGHT HERE!
        sslmode='require'  # <--- CRITICAL: You must add this line for Neon!
    )
    return conn

@app.route('/api/rating', methods=['POST'])
def receive_rating():
    print("\n========== INCOMING LOCAL REQUEST DETECTED ==========")
    raw_data = request.get_data(as_text=True)
    print(f"Raw Request Payload: {raw_data}")

    data = request.get_json(silent=True)
    if not data:
        print("ERROR: Could not parse payload as JSON.")
        return jsonify({"error": "Invalid JSON"}), 400

    q_id = data.get('question_id')
    score = data.get('rating_score')
    print(f"Parsed Content -> Question ID: {q_id} | Rating Score: {score}")

    try:
        print("Attempting connection to local PostgreSQL database...")
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO feedback_ratings (question_id, rating_score) VALUES (%s, %s)",
            (q_id, score)
        )
        conn.commit()
        cur.close()
        conn.close()
        print("DATABASE SUCCESS! Row added to PostgreSQL.")
        return jsonify({"status": "success", "message": "Saved to database"}), 201

    except Exception as e:
        # LOCAL FALLBACK ROUTINE:
        # If your local database is paused or missing the table during your class demo,
        # it prints the error locally but keeps the ESP32 happy!
        print(f"DATABASE NOT READY YET: {e}")
        print("NETWORK TEST MODE: Sending dummy 201 success to ESP32 anyway!")
        print("===================================================\n")
        return jsonify({"status": "network_test_success", "db_error": str(e)}), 201

if __name__ == '__main__':
    # Binds to 0.0.0.0 so devices on your hotspot network can see it
    app.run(host='0.0.0.0', port=5000)
