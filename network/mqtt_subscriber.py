import json
import os
import sqlite3
import paho.mqtt.client as mqtt

# --- CONFIGURATION ---
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC = "ecowatt/telemetry"

# Explicit absolute path to ensure correct database targeting on Windows
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(os.path.dirname(BASE_DIR), "database")
DB_PATH = os.path.join(DB_DIR, "ecowatt.db")


def init_db():
    """Ensures the database directory and telemetry table exist with relay_state."""
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR, exist_ok=True)

    print(f"Connecting to database at: {DB_PATH}")
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


def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("Connected to MQTT Broker successfully!")
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"Failed to connect, return code {rc}")


def on_message(client, userdata, msg):
    try:
        payload_str = msg.payload.decode("utf-8")
        data = json.loads(payload_str)
        print(f"📥 Received ESP32 Telemetry: {data}")

        # Extract values using standardized fallback keys (nominal 215V midpoint fallback)
        v_rms = float(data.get("voltage", data.get("voltage_rms", 215.0)))
        c_rms = float(data.get("current", data.get("current_rms", 0.0)))
        p_act = float(data.get("power", data.get("active_power", 0.0)))
        freq = float(data.get("frequency", 50.0))
        pf = float(data.get("power_factor", 0.95))
        dv_dt = float(data.get("dv_dt", 0.0))
        vhs = float(data.get("vhs_score", data.get("vhs", 95.0)))
        fault = int(data.get("fault_flag", 0))
        relay_state = str(data.get("relay_state", "CLOSED"))

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(
            """
            INSERT INTO telemetry (voltage_rms, current_rms, active_power, frequency, power_factor, dv_dt, vhs_score, fault_flag, relay_state)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (v_rms, c_rms, p_act, freq, pf, dv_dt, vhs, fault, relay_state),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ Error processing message: {e}")


if __name__ == "__main__":
    init_db()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    print(f"Connecting to broker {MQTT_BROKER}:{MQTT_PORT}...")
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_forever()