from datetime import datetime
import json
import os
import sqlite3
import sys
import threading
import time
from dotenv import load_dotenv
import numpy as np
import pandas as pd
import paho.mqtt.publish as mqtt_publish
import plotly.graph_objects as go
import streamlit as st

# --- RESOLVE MODULE PATH FOR ROOT DIRECTORY ('agents', 'data', etc.) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Import external modules safely with fallback if running isolated in Streamlit Cloud
try:
    from agents.gemini_agent import generate_ai_advisory
    from agents.report_generator import generate_comprehensive_audit_pdf
    from network.mqtt_subscriber import run_mqtt_background_loop
    MQTT_IMPORT_SUCCESS = True
except ImportError:
    MQTT_IMPORT_SUCCESS = False

# --- AUTOMATIC BACKGROUND MQTT WORKER FOR STREAMLIT CLOUD ---
@st.cache_resource
def initialize_mqtt_background_worker():
    """Starts the MQTT subscriber thread once in the background if available."""
    if MQTT_IMPORT_SUCCESS:
        try:
            thread = threading.Thread(target=run_mqtt_background_loop, daemon=True)
            thread.start()
            return "Started"
        except Exception:
            return "Failed"
    return "Skipped"

# Initialize background MQTT listener on app boot
initialize_mqtt_background_worker()

# Load environment variables from .env file if present (with override to ensure fresh load)
load_dotenv(override=True)

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="EcoWatt AI Guardian",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Robust Database Path Setup
DB_DIR = os.path.join(PROJECT_ROOT, "database")
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR, exist_ok=True)
DB_FILE = os.path.join(DB_DIR, "ecowatt.db")

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
TOPIC_WIFI_SET = "ecowatt/wifi/update"

# --- CUSTOM CSS ---
st.markdown(
    """
<style>
    .main { background-color: #0E1117; }
    .metric-card {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 8px;
        padding: 10px 14px;
        text-align: center;
        margin-bottom: 8px;
    }
    .metric-title {
        font-size: 11px;
        color: #8B949E;
        text-transform: uppercase;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    .metric-value {
        font-size: 22px;
        font-weight: 700;
        color: #F0F6FC;
        margin-top: 2px;
    }
    .metric-sub {
        font-size: 11px;
        font-weight: 500;
        margin-top: 2px;
    }
    .badge-pos { color: #3FB950; }
    .badge-neg { color: #F85149; }
    .badge-warn { color: #D29922; }
    .relay-closed { color: #3FB950; font-weight: bold; }
    .relay-open { color: #F85149; font-weight: bold; }
</style>
""",
    unsafe_allow_html=True,
)


# --- DATABASE FETCH (NO SIMULATION FALLBACK) ---
def fetch_telemetry(limit=40):
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query(
            f"SELECT * FROM telemetry ORDER BY id DESC LIMIT {limit}", conn
        )
        conn.close()

        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            if "frequency" not in df.columns:
                df["frequency"] = 0.0
            if "vhs_score" not in df.columns:
                df["vhs_score"] = 0.0

            df = df.sort_values(by="id", ascending=True).reset_index(drop=True)
            if "voltage_rms" in df.columns and len(df) >= 3:
                voltages = df["voltage_rms"].tolist()
                dv_dt_list = [0.0] * len(voltages)
                for i in range(1, len(voltages)):
                    dv_dt_list[i] = round(voltages[i] - voltages[i - 1], 2)
                df["dv_dt"] = dv_dt_list
            elif "dv_dt" not in df.columns:
                df["dv_dt"] = 0.0

            df["pred_voltage"] = df["voltage_rms"] + (df["dv_dt"] * 3.0)
            return df
    except Exception:
        pass  

    return pd.DataFrame()


# Fetch data and evaluate connection timeout
df = fetch_telemetry(40)

is_hardware_connected = True
if df.empty:
    is_hardware_connected = False
    df = pd.DataFrame({
        "timestamp": [datetime.now()],
        "voltage_rms": [0.0],
        "current_rms": [0.0],
        "active_power": [0.0],
        "frequency": [0.0],
        "power_factor": [0.0],
        "dv_dt": [0.0],
        "pred_voltage": [0.0],
        "vhs_score": [0.0],
        "fault_flag": [1]
    })
else:
    latest = df.iloc[-1]
    latest_dt = pd.to_datetime(latest["timestamp"])
    current_epoch = datetime.now().timestamp()
    record_epoch = latest_dt.timestamp()
    time_diff = current_epoch - record_epoch

    # Strict 15-second heartbeat threshold check
    if time_diff > 15.0 or time_diff < -5.0:
        is_hardware_connected = False
        df["voltage_rms"] = 0.0
        df["current_rms"] = 0.0
        df["active_power"] = 0.0
        df["frequency"] = 0.0
        df["power_factor"] = 0.0
        df["pred_voltage"] = 0.0
        df["dv_dt"] = 0.0
        df["vhs_score"] = 0.0
        df["fault_flag"] = 1

latest = df.iloc[-1] if not df.empty else {
    "voltage_rms": 0.0, "current_rms": 0.0, "active_power": 0.0, 
    "frequency": 0.0, "power_factor": 0.0, "dv_dt": 0.0, 
    "pred_voltage": 0.0, "vhs_score": 0.0, "fault_flag": 1
}

# --- ROBUST 48H ENERGY CALCULATION WITH HARDWARE TIMEOUT PROTECTION ---
if not is_hardware_connected or latest.get("voltage_rms", 0) == 0:
    energy_48h = 0.0
    carbon_48h = 0.0
else:
    valid_df = df[df["active_power"] >= 0.0]
    if not valid_df.empty:
        avg_power_watts = float(valid_df["active_power"].clip(lower=0.0, upper=10000.0).mean())
    else:
        avg_power_watts = 0.0

    if avg_power_watts > 0.1:
        st.session_state["persistent_avg_power"] = avg_power_watts
    else:
        avg_power_watts = st.session_state.get("persistent_avg_power", 5.0)

    energy_48h = (avg_power_watts * 48.0) / 1000.0
    carbon_48h = energy_48h * 0.82


# --- SIDEBAR CONTROLS ---
with st.sidebar:
    st.markdown("### ⚡ EcoWatt AI Guardian")
    st.caption("Edge Controller & Provisioning Gateway")

    # Connection Status Indicator
    if is_hardware_connected:
        st.markdown(
            "🟢 **Hardware Status:** `ONLINE (LIVE)`", unsafe_allow_html=True
        )
    else:
        st.markdown(
            "🔴 **Hardware Status:** `OFFLINE (STALE / TIMEOUT)`",
            unsafe_allow_html=True,
        )

    col_b1, col_b2 = st.columns(2)
    with col_b1:
        st.button("▶ Start", use_container_width=True)
    with col_b2:
        st.button("⏸ Pause", use_container_width=True)

    st.markdown("---")
    st.markdown("#### ⚙ Tariff & Cost Configuration")
    tariff_unit = st.number_input(
        "Electricity Rate (₹ / kWh)",
        min_value=1.0,
        max_value=30.0,
        value=8.5,
        step=0.5,
    )

    st.markdown("---")
    st.markdown("#### 📶 Remote ESP32 Wi-Fi Setup")
    with st.expander("Configure Network Credentials", expanded=False):
        new_ssid = st.text_input("SSID", placeholder="Network Name")
        new_pass = st.text_input(
            "Password", type="password", placeholder="Network Password"
        )
        if st.button("📡 Dispatch Credentials", use_container_width=True):
            if new_ssid:
                try:
                    mqtt_publish.single(
                        TOPIC_WIFI_SET,
                        payload=json.dumps({"ssid": new_ssid, "pass": new_pass}),
                        hostname=MQTT_BROKER,
                        port=MQTT_PORT,
                        retain=False,
                    )
                    st.success("Credentials dispatched to ESP32!")
                except Exception as e:
                    st.error(f"MQTT Error: {e}")

    st.markdown("---")
    auto_refresh = st.checkbox("Live Polling (1s)", value=True)

    st.markdown("---")
    st.markdown("#### 🕒 Reporting")
    gemini_summary = st.session_state.get(
        "gemini_cache",
        "Nominal operational state within strict 200V-230V envelope. No severe electrical hazards detected.",
    )
    
    # Generate PDF safely with module check and fallback
    pdf_data = None
    if MQTT_IMPORT_SUCCESS:
        try:
            pdf_data = generate_comprehensive_audit_pdf(
                df=df,
                latest=latest,
                gemini_summary=gemini_summary,
                tariff_rate=tariff_unit,
                aggregated_kwh=energy_48h,
                aggregated_carbon=carbon_48h
            )
        except Exception:
            pdf_data = None

    if pdf_data is None:
        from io import BytesIO
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        c.drawString(50, 750, "EcoWatt AI Guardian - Power Audit Report")
        c.drawString(50, 730, f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        c.drawString(50, 700, f"Voltage: {latest.get('voltage_rms', 0.0):.2f} V")
        c.drawString(50, 680, f"Current: {latest.get('current_rms', 0.0):.2f} A")
        c.drawString(50, 660, f"Active Power: {latest.get('active_power', 0.0):.1f} W")
        c.drawString(50, 640, f"Energy (48h): {energy_48h:.4f} kWh")
        c.drawString(50, 620, f"Summary: {gemini_summary}")
        c.save()
        pdf_data = buffer.getvalue()

    st.download_button(
        label="⚙ Compile Audit PDF",
        data=pdf_data,
        file_name=f"EcoWatt_Audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )


# --- MAIN DASHBOARD INTERFACE ---
st.title("⚡ EcoWatt AI Guardian")
st.caption(
    "Real-Time Telemetry (Strict 200V-230V AC) | Predictive Protection | Energy Auditing | Multi-Agent AI"
)

cost_48h = energy_48h * tariff_unit

# --- ROW 1: PRIMARY ELECTRICAL METRICS ---
r1_c1, r1_c2, r1_c3, r1_c4, r1_c5, r1_c6 = st.columns(6)

with r1_c1:
    v_delta = f"{latest.get('dv_dt', 0.0):+.2f} V/s"
    v_class = (
        "badge-neg"
        if latest.get("dv_dt", 0.0) < -1.0
        else ("badge-warn" if latest.get("dv_dt", 0.0) > 1.0 else "badge-pos")
    )
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">Live Voltage</div>
            <div class="metric-value">{latest.get('voltage_rms', 0.0):.2f} V</div>
            <div class="metric-sub {v_class}">{v_delta}</div>
        </div>
    """,
        unsafe_allow_html=True,
    )

with r1_c2:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">Live Current</div>
            <div class="metric-value">{latest.get('current_rms', 0.0):.2f} A</div>
            <div class="metric-sub badge-pos">Active Load</div>
        </div>
    """,
        unsafe_allow_html=True,
    )

with r1_c3:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">Active Power</div>
            <div class="metric-value">{latest.get('active_power', 0.0):.1f} W</div>
            <div class="metric-sub badge-pos">Real Draw</div>
        </div>
    """,
        unsafe_allow_html=True,
    )

with r1_c4:
    freq_val = latest.get("frequency", 0.0)
    freq_class = "badge-pos" if (49.8 <= freq_val <= 50.2 and freq_val > 0) else "badge-warn"
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">Grid Frequency</div>
            <div class="metric-value">{freq_val:.2f} Hz</div>
            <div class="metric-sub {freq_class}">{"Nominal 50Hz" if freq_val > 0 else "Disconnected"}</div>
        </div>
    """,
        unsafe_allow_html=True,
    )

with r1_c5:
    pf_val = latest.get("power_factor", 0.0)
    pf_class = "badge-pos" if (pf_val >= 0.90 and pf_val > 0) else "badge-warn"
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">Power Factor</div>
            <div class="metric-value">{pf_val:.2f}</div>
            <div class="metric-sub {pf_class}">{"Good" if (pf_val >= 0.90 and pf_val > 0) else "Offline"}</div>
        </div>
    """,
        unsafe_allow_html=True,
    )

with r1_c6:
    vhs = latest.get("vhs_score", 0.0)
    vhs_class = (
        "badge-pos"
        if vhs >= 80
        else ("badge-warn" if vhs >= 60 else "badge-neg")
    )
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">Health (VHS)</div>
            <div class="metric-value">{vhs:.1f} / 100</div>
            <div class="metric-sub {vhs_class}">{"Optimal" if vhs >= 80 else "Degraded"}</div>
        </div>
    """,
        unsafe_allow_html=True,
    )

# --- ROW 2: FORECAST & AGGREGATED SUSTAINABILITY METRICS ---
r2_c1, r2_c2, r2_c3, r2_c4, r2_c5 = st.columns(5)

with r2_c1:
    pred_v = latest.get("pred_voltage", 0.0)
    pred_delta = pred_v - latest.get("voltage_rms", 0.0)
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">Predicted (+3s)</div>
            <div class="metric-value">{pred_v:.2f} V</div>
            <div class="metric-sub badge-warn">{pred_delta:+.2f} V Trend</div>
        </div>
    """,
        unsafe_allow_html=True,
    )

with r2_c2:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">48h Energy</div>
            <div class="metric-value">{energy_48h:.4f} kWh</div>
            <div class="metric-sub badge-pos">Aggregated</div>
        </div>
    """,
        unsafe_allow_html=True,
    )

with r2_c3:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">Estimated Cost</div>
            <div class="metric-value">₹ {cost_48h:.2f}</div>
            <div class="metric-sub badge-pos">@ ₹{tariff_unit}/unit</div>
        </div>
    """,
        unsafe_allow_html=True,
    )

with r2_c4:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">48h Carbon</div>
            <div class="metric-value">{carbon_48h:.4f} kg</div>
            <div class="metric-sub badge-pos">CO2 Emissions</div>
        </div>
    """,
        unsafe_allow_html=True,
    )

with r2_c5:
    relay_status = (
        "CLOSED" if latest.get("fault_flag", 0) == 0 and is_hardware_connected else "TRIPPED"
    )
    relay_style = (
        "relay-closed" if relay_status == "CLOSED" else "relay-open"
    )
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">Relay State</div>
            <div class="metric-value {relay_style}">● {relay_status}</div>
            <div class="metric-sub badge-pos">Auto-Protected</div>
        </div>
    """,
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# --- MULTI-AGENT INTELLIGENCE ENGINE (Strict 200V-230V Envelope) ---
st.markdown("### ⚙ Multi-Agent AI Intelligence Engine")

tab_fault, tab_energy, tab_recom, tab_sust, tab_info, tab_gemini = st.tabs([
    "⚡ Fault Agent",
    "🔋 Energy Agent",
    "💡 Recommendation Agent",
    "🌱 Sustainability Agent",
    "ℹ Information Agent",
    "✨ Gemini AI Intelligence",
])

with tab_fault:
    if not is_hardware_connected:
        st.error(
            "🔴 **HARDWARE DISCONNECTED / TIMEOUT:** No telemetry packets received from ESP32 edge node in >15s. Safety interlock engaged."
        )
    elif latest.get("voltage_rms", 0.0) > 230.0 or (0 < latest.get("voltage_rms", 0.0) < 200.0):
        st.error(
            f"⚠️ **CRITICAL VOLTAGE THRESHOLD BREACH:** Measured RMS voltage ({latest.get('voltage_rms', 0.0):.1f}V) violates strict 200V-230V AC safety envelope! Hardware relay latch active."
        )
    elif abs(latest.get("dv_dt", 0.0)) > 1.5:
        st.warning(
            f"⚡ **HIGH TRANSIENT VOLTAGE DRIFT (dV/dt):** Rate of change elevated at **{latest.get('dv_dt', 0.0):+.2f} V/s**. Forward +3s projection: **{latest.get('pred_voltage', 0.0):.2f}V**. Preemptive soft-trip monitoring active."
        )
    else:
        st.success(
            f"✅ **GRID STABILITY VERIFIED:** Line parameters operate strictly within the nominal 200V-230V AC target window. Voltage Health Score: **{latest.get('vhs_score', 95.0):.1f}/100**."
        )

with tab_energy:
    st.info(f"""
    🔋 **Real-Time Active Power & Load Telemetry:**
    - **Active Real Draw:** `{latest.get('active_power', 0.0):.1f} W` | **RMS Current:** `{latest.get('current_rms', 0.0):.2f} A`
    - **Grid Frequency:** `{latest.get('frequency', 0.0):.2f} Hz` (Nominal 50Hz Standard)
    - **Accumulated 48-Hour Projection:** `{energy_48h:.4f} kWh` | **Estimated Tariff Cost:** `₹{cost_48h:.2f}` (@ ₹{tariff_unit}/kWh)
    """)

with tab_recom:
    pf_check = latest.get("power_factor", 0.0)
    v_check = latest.get("voltage_rms", 0.0)
    if not is_hardware_connected:
        st.warning("💡 **System Offline:** Reconnect hardware node to resume automated load distribution recommendations.")
    elif pf_check < 0.90 and pf_check > 0:
        st.warning(
            f"💡 **Power Factor Correction Required ({pf_check:.2f}):** Inductive phase lag detected across distribution lines. Integrating automated shunt capacitor bank compensation will eliminate reactive power penalties."
        )
    elif v_check < 200.0 and v_check > 0:
        st.warning(
            f"💡 **Undervoltage Mitigation ({v_check:.1f}V):** Line voltage depressed below lower 200V limit. Recommend shedding heavy inductive motor loads to prevent thermal coil degradation."
        )
    elif v_check > 230.0:
        st.warning(
            f"💡 **Overvoltage Suppression ({v_check:.1f}V):** Line voltage exceeding upper 230V limit. Semiconductor protection interlocks primed."
        )
    else:
        st.success(
            f"💡 **Optimal Power Distribution:** Voltage ({v_check:.1f}V) and Power Factor ({pf_check:.2f}) operating at peak efficiency within the 200V-230V window. No immediate load shedding required."
        )

with tab_sust:
    st.info(f"""
    🌱 **Eco-Compliance & Sustainability Analytics:**
    - **Total Carbon Footprint:** `{carbon_48h:.4f} kg CO₂` generated over the active 48-hour window.
    - **Rooftop Solar PV Offset Potential:** Implementing a 3kW peak solar array can offset approximately **{(energy_48h * 0.75):.2f} kWh** of active grid reliance, reducing facility carbon emissions by ~**{(carbon_48h * 0.75):.2f} kg CO₂**.
    """)

with tab_info:
    st.write("""
    ℹ️ **Edge Node Hardware Specifications & Diagnostics:**
    - **Microcontroller Core:** ESP32-S3-N16R8 Dual-Core Tensilica Xtensa LX7 @ 240MHz
    - **Telemetry Sensor:** PZEM-004T v3.0 Bi-directional AC Energy Monitor
    - **Data Pipeline:** HiveMQ MQTT Broker (`broker.hivemq.com`) $\rightarrow$ SQLite Local Telemetry History $\rightarrow$ Streamlit Reactive UI
    - **Safety Compliance:** IEEE 1159 Standard for Power Quality Monitoring (Strict 200V-230V Envelope)
    """)

with tab_gemini:
    if st.button("✨ Query Gemini AI Advisor", use_container_width=True):
        with st.spinner("Analyzing high-frequency electrical vectors with Gemini AI..."):
            current_sensor_dict = {
                "voltage": latest.get("voltage_rms", 0.0),
                "current": latest.get("current_rms", 0.0),
                "power": latest.get("active_power", 0.0),
                "power_factor": latest.get("power_factor", 0.0)
            }
            prediction_dict = {
                "rate_of_change": latest.get("dv_dt", 0.0),
                "v_predicted": latest.get("pred_voltage", 0.0),
                "predicted_fault": "PREDICTED OVER-VOLTAGE" if latest.get("pred_voltage", 0.0) > 230 else ("PREDICTED UNDER-VOLTAGE" if latest.get("pred_voltage", 0.0) < 200 else "NONE"),
                "action_required": latest.get("pred_voltage", 0.0) > 230 or latest.get("pred_voltage", 0.0) < 200
            }
            
            risk_lvl = "CRITICAL" if latest.get("fault_flag", 0) == 1 else "NORMAL"
            fault_stat = "TRIPPED" if latest.get("fault_flag", 0) == 1 else "NORMAL"

            if MQTT_IMPORT_SUCCESS:
                gemini_out = generate_ai_advisory(
                    sensor_data=current_sensor_dict,
                    vhs_score=int(latest.get("vhs_score", 0)),
                    risk_level=risk_lvl,
                    fault_status=fault_stat,
                    prediction=prediction_dict
                )
            else:
                gemini_out = "Gemini AI module currently unavailable in isolated cloud environment."
            st.session_state["gemini_cache"] = gemini_out

    if "gemini_cache" in st.session_state:
        st.markdown(st.session_state["gemini_cache"])
    else:
        st.caption("Click above to run real-time generative diagnostics on current electrical stability and energy efficiency.")

st.markdown("<br>", unsafe_allow_html=True)

# --- VISUALIZATION CHARTS (200V - 230V Envelope) ---
col_g1, col_g2 = st.columns(2)

with col_g1:
    st.markdown("#### 📈 Voltage Horizon & Strict 200V-230V Limits")
    fig_v = go.Figure()
    fig_v.add_trace(go.Scatter(
        x=df["timestamp"].dt.strftime("%H:%M:%S"),
        y=df["voltage_rms"],
        mode="lines+markers",
        name="RMS Voltage (V)",
        line=dict(color="#00F5D4", width=2),
    ))
    fig_v.add_trace(go.Scatter(
        x=df["timestamp"].dt.strftime("%H:%M:%S"),
        y=df["pred_voltage"],
        mode="lines",
        name="Predicted (+3s)",
        line=dict(color="#FFAA00", dash="dash"),
    ))
    fig_v.add_hline(
        y=230.0,
        line_dash="dash",
        line_color="#FF4B4B",
        annotation_text="Over-Voltage Limit (230V)",
    )
    fig_v.add_hline(
        y=200.0,
        line_dash="dash",
        line_color="#FF4B4B",
        annotation_text="Under-Voltage Limit (200V)",
    )
    fig_v.add_hline(
        y=215.0,
        line_dash="dot",
        line_color="#00E676",
        annotation_text="Nominal Midpoint (215V)",
    )
    fig_v.update_layout(
        height=320,
        template="plotly_dark",
        paper_bgcolor="#0E1117",
        plot_bgcolor="#161B22",
        margin=dict(l=10, r=10, t=25, b=20),
        xaxis=dict(tickangle=-90),
    )
    st.plotly_chart(fig_v, use_container_width=True)

with col_g2:
    st.markdown("#### 📊 Current & Power Profile")
    fig_p = go.Figure()
    fig_p.add_trace(go.Scatter(
        x=df["timestamp"].dt.strftime("%H:%M:%S"),
        y=df["active_power"],
        mode="lines",
        name="Active Power (W)",
        line=dict(color="#76FF03", width=2),
        fill="tozeroy",
    ))
    fig_p.add_trace(go.Scatter(
        x=df["timestamp"].dt.strftime("%H:%M:%S"),
        y=df["current_rms"] * 100,
        mode="lines",
        name="Current (x100 A)",
        line=dict(color="#00E5FF", dash="dot"),
    ))
    fig_p.update_layout(
        height=320,
        template="plotly_dark",
        paper_bgcolor="#0E1117",
        plot_bgcolor="#161B22",
        margin=dict(l=10, r=10, t=25, b=20),
        xaxis=dict(tickangle=-90),
    )
    st.plotly_chart(fig_p, use_container_width=True)

# --- AUTO-REFRESH LOOP ---
if auto_refresh:
    time.sleep(1)
    st.rerun()
