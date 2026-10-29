import os
import sqlite3
import time
from sensor_data import get_sensor_data


def start_logger():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Align path to database/ecowatt.db
    db_path = os.path.abspath(
        os.path.join(current_dir, "..", "database", "ecowatt.db")
    )
    print(f"Connecting to database at {db_path}...")

    previous_voltage = 215.0  # Default to 215V nominal midpoint

    while True:
        try:
            data = get_sensor_data()

            voltage = data.get("voltage", 215.0)
            current = data.get("current", 0.0)
            power = data.get("power", voltage * current)
            frequency = data.get("frequency", 50.0)
            power_factor = data.get("power_factor", 0.95)
            
            # Compute dynamic dV/dt and VHS (centered around 215V nominal)
            dv_dt = round(voltage - previous_voltage, 2)
            previous_voltage = voltage
            
            voltage_deviation = abs(voltage - 215.0)
            pf_penalty = max(0.0, (0.85 - power_factor) * 50.0)
            vhs_score = max(0.0, round(100.0 - (1.5 * voltage_deviation + abs(dv_dt) * 2.0 + pf_penalty), 1))
            
            # Updated fault flag for 200V - 230V AC limits
            fault_flag = 1 if (voltage > 230.0 or (voltage > 0 and voltage < 200.0)) else 0
            relay_state = "TRIPPED" if fault_flag == 1 else "CLOSED"

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Ensure table has all necessary columns including relay_state
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

            cursor.execute(
                """
                    INSERT INTO telemetry (
                        voltage_rms, current_rms, active_power, frequency,
                        power_factor, dv_dt, vhs_score, fault_flag, relay_state
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    voltage,
                    current,
                    power,
                    frequency,
                    power_factor,
                    dv_dt,
                    vhs_score,
                    fault_flag,
                    relay_state,
                ),
            )
            conn.commit()
            conn.close()

            print(f"Logged -> V: {voltage}V, I: {current}A, State: {relay_state}")
        except Exception as e:
            print(f"Logging error: {e}")

        time.sleep(1)


if __name__ == "__main__":
    start_logger()