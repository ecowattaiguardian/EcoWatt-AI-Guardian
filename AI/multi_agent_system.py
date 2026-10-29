# AI/multi_agent_system.py
import numpy as np
from datetime import datetime

class MultiAgentSystem:
    def __init__(self, cycle_start_time: datetime, wifi_ssid: str):
        self.cycle_start_time = cycle_start_time
        self.wifi_ssid = wifi_ssid

    def evaluate_grid(
        self, 
        voltage: float, 
        predicted_v: float, 
        pf: float, 
        current: float, 
        power_kw: float, 
        relay_state: str, 
        roc_v: float, 
        total_kwh_48h: float, 
        vhs: float
    ) -> dict:
        """Executes concurrent evaluation across all 5 specialized AI Agents."""
        
        # 1. ⚡ FAULT AGENT
        if relay_state == "TRIPPED (HARD)":
            fault_msg = f"⚠️ **HARD FAULT**: Instantaneous voltage breach ({voltage:.1f}V). Hardware relay locked out."
            fault_status = "error"
        elif relay_state == "TRIPPED (SOFT)":
            fault_msg = f"🚨 **PREDICTIVE SOFT TRIP**: Rapid transient (dV/dt = {roc_v:+.2f} V/s) foresees breach ({predicted_v:.1f}V in +3s)."
            fault_status = "warning"
        elif abs(roc_v) > 2.0:
            fault_msg = f"⚡ **TRANSIENT DRIFT**: Rate of change elevated (dV/dt = {roc_v:+.2f} V/s). Monitoring line."
            fault_status = "warning"
        else:
            fault_msg = "✅ **GRID STABLE**: Parameters and +3s predictive horizon within nominal limits."
            fault_status = "success"

        # 2. 🔋 ENERGY AGENT
        est_cost_48h = total_kwh_48h * 8.0 # ₹8/kWh tariff
        energy_msg = (
            f"⚡ **LIVE DEMAND**: Drawing **{power_kw:.2f} kW** ({current:.1f} A). "
            f"48-Hour Accumulated Consumption: **{total_kwh_48h:.4f} kWh** (~₹{est_cost_48h:.2f})."
        )

        # 3. 💡 RECOMMENDATION AGENT (Personalized Suggestions)
        recs = []
        if pf < 0.88:
            recs.append(f"• **Power Factor Adjustment**: Active PF ({pf:.2f}) is low. Engage local APFC capacitor banks.")
        if voltage < 195.0:
            recs.append(f"• **Low Voltage Isolation**: Undervoltage ({voltage:.1f}V). Shed heavy inductive motor loads.")
        if power_kw > 3.5:
            recs.append(f"• **Peak Load Shading**: High demand ({power_kw:.2f} kW). Stagger appliance startup times.")
        if not recs:
            recs.append("• **Optimal Operation**: Grid operating parameters are nominal. No intervention needed.")
        rec_msg = "\n".join(recs)

        # 4. 🌱 SUSTAINABILITY AGENT
        co2_emitted = total_kwh_48h * 0.82
        solar_offset_kwh = total_kwh_48h * 0.75
        sustain_msg = (
            f"🌱 **CARBON TRACKER**: Footprint = **{co2_emitted:.4f} kg CO₂**. "
            f"Rooftop Solar PV can offset ~**{solar_offset_kwh:.2f} kWh** of active grid demand."
        )

        # 5. ℹ️ INFORMATION AGENT
        elapsed_hrs = (datetime.now() - self.cycle_start_time).total_seconds() / 3600.0
        info_msg = (
            f"ℹ️ **SYSTEM METADATA**: 48h Cycle Progress: **{elapsed_hrs:.2f} / 48.00 Hours** | "
            f"Sampling: 1.0 Hz | VHS Score: **{vhs:.1f}/100** | Active SSID: **{self.wifi_ssid}**"
        )

        return {
            "fault": (fault_msg, fault_status),
            "energy": energy_msg,
            "recommendation": rec_msg,
            "sustainability": sustain_msg,
            "info": info_msg
        }