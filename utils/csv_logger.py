import os
import pandas as pd
from datetime import datetime

# Resolve path to data directory relative to project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE_DIR, "data", "telemetry_history.csv")

def log_telemetry(sensor_data: dict, vhs_score: int, fault_status: str, risk_level: str):
    """
    Logs every telemetry reading to a CSV file for historical graphing and AI trend analysis.
    Supports both standard and MQTT key naming conventions (voltage vs voltage_rms).
    """
    try:
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Extract values with flexible key fallbacks
        voltage = sensor_data.get("voltage") if sensor_data.get("voltage") is not None else sensor_data.get("voltage_rms", 215.0)
        current = sensor_data.get("current") if sensor_data.get("current") is not None else sensor_data.get("current_rms", 0.0)
        power = sensor_data.get("power") if sensor_data.get("power") is not None else sensor_data.get("active_power", 0.0)
        power_factor = sensor_data.get("power_factor", 0.95)
        frequency = sensor_data.get("frequency", 50.0)

        record = {
            "timestamp": timestamp,
            "voltage": voltage,
            "current": current,
            "power": power,
            "power_factor": power_factor,
            "frequency": frequency,
            "vhs": vhs_score,
            "fault": fault_status,
            "risk": risk_level
        }
        
        df_new = pd.DataFrame([record])
        
        # Append to existing file or create with header if missing
        if not os.path.exists(DATA_FILE):
            df_new.to_csv(DATA_FILE, index=False)
        else:
            df_new.to_csv(DATA_FILE, mode='a', header=False, index=False)
    except Exception as e:
        print(f"❌ CSV Logging Error: {e}")

def read_telemetry_history(limit: int = 30) -> pd.DataFrame:
    """
    Reads the last 'limit' records from the telemetry CSV file.
    """
    if not os.path.exists(DATA_FILE):
        return pd.DataFrame()
    
    try:
        df = pd.read_csv(DATA_FILE)
        return df.tail(limit)
    except Exception:
        return pd.DataFrame()