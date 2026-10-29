def detect_fault(voltage: float) -> str:
    """
    Detects electrical line faults based on RMS voltage thresholds (200V - 230V).
    """
    if voltage <= 0.0:
        return "OFFLINE / NO POWER"
    elif voltage > 230.0:
        return "OVER VOLTAGE"
    elif voltage < 200.0:
        return "UNDER VOLTAGE"
    else:
        return "NORMAL"