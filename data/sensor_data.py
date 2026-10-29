import os
import random
import sys

# Add parent directory to path so 'network' can be found
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from network.mqtt_subscriber import get_latest_mqtt_data
except ImportError:
    def get_latest_mqtt_data():
        return {}

# Toggle this flag to switch between synthetic simulation and MQTT stream
USE_MQTT_HARDWARE = True 

def get_sensor_data() -> dict:
    """
    Returns telemetry data from either live MQTT hardware stream 
    or the fallback synthetic simulator (aligned with 200V-230V limits).
    """
    if USE_MQTT_HARDWARE:
        data = get_latest_mqtt_data()
        if data:
            return data
    
    # Fallback / Default Synthetic Simulation (Aligned with 200V - 230V bounds)
    voltage = round(random.uniform(205.0, 225.0), 2)
    
    # Inject occasional transient voltage drop or surge outside 200V-230V (5% probability)
    if random.random() < 0.05:
        voltage = round(random.choice([235.0, 192.0]), 2)

    current = round(random.uniform(0.5, 12.0), 2)
    power_factor = round(random.uniform(0.85, 0.99), 2)
    power = round(voltage * current * power_factor, 2)
    frequency = round(random.uniform(49.8, 50.2), 2)

    return {
        "voltage": voltage,
        "voltage_rms": voltage,
        "current": current,
        "current_rms": current,
        "power": power,
        "active_power": power,
        "power_factor": power_factor,
        "frequency": frequency
    }