def calculate_risk_level(vhs_score: int, fault_status: str) -> str:
    """
    Determines System Risk Level based on Voltage Health Score (VHS) and active fault state.
    
    Ranges:
    0 - 30   : CRITICAL
    31 - 50  : HIGH
    51 - 70  : MEDIUM
    71 - 100 : LOW
    """
    # Normalize inputs for robust case-insensitivity
    f_status = str(fault_status).strip().upper() if fault_status else "NORMAL"
    
    # Ensure VHS score is clamped between 0 and 100
    try:
        score = max(0, min(100, int(vhs_score)))
    except (TypeError, ValueError):
        score = 50  # Default fallback if invalid score passed

    # Immediate safety override if an active hardware fault exists
    if f_status != "NORMAL":
        return "CRITICAL"

    if score <= 30:
        return "CRITICAL"
    elif score <= 50:
        return "HIGH"
    elif score <= 70:
        return "MEDIUM"
    else:
        return "LOW"