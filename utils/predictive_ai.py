import pandas as pd
import numpy as np

def predict_future_fault(df_history: pd.DataFrame, current_voltage: float) -> dict:
    """
    Analyzes historical telemetry data to calculate rate-of-change (dV/dt),
    extrapolates projected voltage 3 seconds ahead, and calculates fault probability (200V - 230V limit).
    """
    if df_history.empty:
        return {
            "rate_of_change": 0.0,
            "v_predicted": current_voltage,
            "trend": "STABLE",
            "fault_probability": 2.0,
            "predicted_fault": "NONE",
            "action_required": False
        }

    # Support both 'voltage' and 'voltage_rms' column naming conventions
    v_col = "voltage" if "voltage" in df_history.columns else ("voltage_rms" if "voltage_rms" in df_history.columns else None)

    if not v_col or len(df_history) < 3:
        return {
            "rate_of_change": 0.0,
            "v_predicted": current_voltage,
            "trend": "STABLE",
            "fault_probability": 2.0,
            "predicted_fault": "NONE",
            "action_required": False
        }

    # Extract recent valid numeric voltage window (last 5 samples)
    voltages = pd.to_numeric(df_history[v_col], errors='coerce').dropna().tail(5).tolist()
    
    if len(voltages) < 2:
        return {
            "rate_of_change": 0.0,
            "v_predicted": current_voltage,
            "trend": "STABLE",
            "fault_probability": 2.0,
            "predicted_fault": "NONE",
            "action_required": False
        }

    # Calculate First Derivative: dV/dt (Average change per sample/second)
    dv_dt = round(float(np.mean(np.diff(voltages))), 2)

    # Calculate 3-Second Projected Voltage
    v_predicted = round(current_voltage + (dv_dt * 3.0), 2)

    # Determine Trend Direction
    if dv_dt > 1.5:
        trend = "RISING RAPIDLY"
    elif dv_dt < -1.5:
        trend = "FALLING RAPIDLY"
    else:
        trend = "STABLE"

    # Evaluate Predictive Risk & Probability for 200V - 230V bounds
    predicted_fault = "NONE"
    fault_prob = 4.0
    action_required = False

    if v_predicted > 230.0:
        predicted_fault = "PREDICTED OVER-VOLTAGE"
        fault_prob = min(99.0, round(75.0 + (v_predicted - 230.0) * 4.0, 1))
        action_required = True
    elif v_predicted < 200.0:
        predicted_fault = "PREDICTED UNDER-VOLTAGE"
        fault_prob = min(99.0, round(75.0 + (200.0 - v_predicted) * 4.0, 1))
        action_required = True
    elif dv_dt > 1.5 or dv_dt < -1.5:
        predicted_fault = "GRID INSTABILITY WARNING"
        fault_prob = 55.0

    return {
        "rate_of_change": dv_dt,
        "v_predicted": v_predicted,
        "trend": trend,
        "fault_probability": fault_prob,
        "predicted_fault": predicted_fault,
        "action_required": action_required
    }