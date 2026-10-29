def calculate_protection_status(risk_level: str, fault_status: str) -> dict:
    """
    Translates Risk Level and Fault Status into action commands for relay and UI alerts.
    Normalized for case-insensitivity and whitespace resilience.
    """
    # Normalize inputs safely
    r_level = str(risk_level).strip().upper() if risk_level else "NORMAL"
    f_status = str(fault_status).strip().upper() if fault_status else "NORMAL"

    if f_status != "NORMAL":
        return {
            "status": "CRITICAL",
            "relay_state": "OFF (TRIPPED)",
            "mode": "AUTOMATIC FAULT TRIP",
            "alert_type": "error"
        }
    elif r_level == "CRITICAL":
        return {
            "status": "PROTECTION ACTIVE",
            "relay_state": "OFF (PREDICTIVE TRIP)",
            "mode": "AI SOFT-TRIP ENGAGED",
            "alert_type": "error"
        }
    elif r_level in ["HIGH", "MEDIUM"]:
        return {
            "status": "WARNING",
            "relay_state": "ON (MONITORING)",
            "mode": "ELEVATED VIGILANCE",
            "alert_type": "warning"
        }
    else:
        return {
            "status": "SAFE",
            "relay_state": "ON (CLOSED)",
            "mode": "NOMINAL OPERATION",
            "alert_type": "success"
        }