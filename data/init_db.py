import os
import sqlite3

# --- CONFIGURATION & ROBUST PATH RESOLUTION ---
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC = "ecowatt/telemetry"

# Robust path resolution independent of execution directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DB_DIR = os.path.join(PROJECT_ROOT, "database")
DB_PATH = os.path.join(DB_DIR, "ecowatt.db")


def init_db():
    """Ensures the database directory and telemetry table exist."""
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            voltage_rms REAL,
            current_rms REAL,
            active_power REAL,
            frequency REAL,
            power_factor REAL,
            dv_dt REAL,
            vhs_score REAL,
            fault_flag INTEGER,
            relay_state TEXT
        )
    """)
    conn.commit()
    conn.close()
    print(f"Database initialized successfully at: {DB_PATH}")


if __name__ == "__main__":
    init_db()