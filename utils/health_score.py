def calculate_vhs(voltage: float, power_factor: float, fault_status: str) -> dict:
    if voltage <= 0.0:
        return {
            "total_vhs": 0, "s_voltage": 0.0, "s_fault": 0.0, "s_pf": 0.0, "s_protection": 0.0
        }

    voltage_deviation = abs(voltage - 215.0)  # Centered around the midpoint (215V)
    s_voltage = max(0.0, 40.0 - (voltage_deviation * 1.2))

    s_fault = 20.0 if fault_status == "NORMAL" else 0.0
    s_pf = max(0.0, min(20.0, power_factor * 20.0))

    # Updated optimal protection band for 200V - 230V
    if 200.0 <= voltage <= 230.0:
        s_protection = 20.0
    else:
        s_protection = max(0.0, 20.0 - (abs(voltage - 215.0) * 0.8))

    total_vhs = int(round(s_voltage + s_fault + s_pf + s_protection))
    return {
        "total_vhs": max(0, min(100, total_vhs)),
        "s_voltage": round(s_voltage, 1),
        "s_fault": round(s_fault, 1),
        "s_pf": round(s_pf, 1),
        "s_protection": round(s_protection, 1)
    }