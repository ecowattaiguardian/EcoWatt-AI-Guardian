import pandas as pd
import numpy as np

def evaluate_reconnection_safety(df_history: pd.DataFrame) -> dict:
    """
    Evaluates whether an isolated load can be safely re-energized
    based on voltage rolling mean, variance, and dV/dt convergence (200V - 230V limit).
    """
    if df_history.empty:
        return {
            "reconnect_allowed": False,
            "reason": "INSUFFICIENT TELEMETRY DATA",
            "mean_v": 0.0,
            "variance_v": 99.0
        }

    # Support both 'voltage' and 'voltage_rms' column naming conventions
    v_col = "voltage" if "voltage" in df_history.columns else ("voltage_rms" if "voltage_rms" in df_history.columns else None)

    if not v_col or len(df_history) < 5:
        return {
            "reconnect_allowed": False,
            "reason": "INSUFFICIENT TELEMETRY DATA OR MISSING COLUMN",
            "mean_v": 0.0,
            "variance_v": 99.0
        }

    # Extract last 10 voltage samples safely
    recent_voltages = pd.to_numeric(df_history[v_col], errors='coerce').dropna().tail(10).tolist()
    
    if len(recent_voltages) < 3:
        return {
            "reconnect_allowed": False,
            "reason": "INSUFFICIENT VALID NUMERIC SAMPLES",
            "mean_v": 0.0,
            "variance_v": 99.0
        }

    mean_v = round(float(np.mean(recent_voltages)), 2)
    var_v = round(float(np.var(recent_voltages)), 2)
    
    # Calculate latest rate-of-change securely
    dv_dt = abs((recent_voltages[-1] - recent_voltages[-3]) / 2.0)

    # Rule Checks for 200V - 230V target window
    mean_safe = 200.0 <= mean_v <= 230.0
    variance_safe = var_v < 3.0       # Tighter variance threshold
    trend_safe = dv_dt < 0.5          # Stricter transient trend rate

    if mean_safe and variance_safe and trend_safe:
        return {
            "reconnect_allowed": True,
            "reason": "GRID STABILIZED WITHIN 200V-230V BAND — HIGH STABILITY INDEX",
            "mean_v": mean_v,
            "variance_v": var_v
        }
    else:
        reasons = []
        if not mean_safe:
            reasons.append(f"Mean voltage out of bounds 200-230V ({mean_v}V)")
        if not variance_safe:
            reasons.append(f"High variance ({var_v} >= 3.0)")
        if not trend_safe:
            reasons.append(f"Active transient trend ({dv_dt:.1f} V/s)")
            
        return {
            "reconnect_allowed": False,
            "reason": f"HOLDING RECONNECT: {', '.join(reasons)}",
            "mean_v": mean_v,
            "variance_v": var_v
        }