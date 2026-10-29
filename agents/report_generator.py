# agents/report_generator.py
from datetime import datetime
import io
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generate_comprehensive_audit_pdf(df, latest, gemini_summary, tariff_rate, aggregated_kwh, aggregated_carbon):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter, 
        rightMargin=36, 
        leftMargin=36, 
        topMargin=36, 
        bottomMargin=36
    )
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle', 
        parent=styles['Heading1'], 
        fontSize=14, 
        textColor=colors.HexColor('#0F172A'), 
        spaceAfter=3
    )
    subtitle_style = ParagraphStyle(
        'DocSub', 
        parent=styles['Normal'], 
        fontSize=8.5, 
        textColor=colors.HexColor('#64748B'), 
        spaceAfter=8
    )
    heading_style = ParagraphStyle(
        'SectionHead', 
        parent=styles['Heading2'], 
        fontSize=10, 
        textColor=colors.HexColor('#1E293B'), 
        spaceBefore=6, 
        spaceAfter=3
    )
    body_style = ParagraphStyle(
        'BodyTextCustom', 
        parent=styles['Normal'], 
        fontSize=7.5, 
        textColor=colors.HexColor('#334155'), 
        leading=10, 
        spaceAfter=2
    )

    # 1. Header Block
    story.append(Paragraph("<b>EcoWatt AI Guardian — Professional Electrical & Compliance Audit</b>", title_style))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Standard: IEEE 1159 Power Quality (Strict 200V-230V AC Window)", subtitle_style))
    story.append(Spacer(1, 2))

    # Safely extract latest dictionary values or Series properties
    v_rms = float(latest.get('voltage_rms', 0.0) if hasattr(latest, 'get') else latest['voltage_rms'])
    i_rms = float(latest.get('current_rms', 0.0) if hasattr(latest, 'get') else latest['current_rms'])
    p_act = float(latest.get('active_power', 0.0) if hasattr(latest, 'get') else latest['active_power'])
    freq = float(latest.get('frequency', 0.0) if hasattr(latest, 'get') else latest['frequency'])
    pf = float(latest.get('power_factor', 0.0) if hasattr(latest, 'get') else latest['power_factor'])
    vhs = float(latest.get('vhs_score', 0.0) if hasattr(latest, 'get') else latest['vhs_score'])
    pred_v = float(latest.get('pred_voltage', 0.0) if hasattr(latest, 'get') else latest['pred_voltage'])
    fault_flg = int(latest.get('fault_flag', 1) if hasattr(latest, 'get') else latest['fault_flag'])

    # 2. Live Snapshot Table Data
    story.append(Paragraph("<b>Current Snapshot Telemetry (Live Edge State):</b>", heading_style))
    
    live_data = [
        [Paragraph("<b>Parameter</b>", body_style), Paragraph("<b>Value / Status</b>", body_style), Paragraph("<b>Parameter</b>", body_style), Paragraph("<b>Value / Status</b>", body_style)],
        [Paragraph("RMS Voltage", body_style), Paragraph(f"{v_rms:.2f} V", body_style), Paragraph("Grid Frequency", body_style), Paragraph(f"{freq:.2f} Hz", body_style)],
        [Paragraph("RMS Current", body_style), Paragraph(f"{i_rms:.2f} A", body_style), Paragraph("Power Factor", body_style), Paragraph(f"{pf:.2f}", body_style)],
        [Paragraph("Active Power", body_style), Paragraph(f"{p_act:.1f} W", body_style), Paragraph("Voltage Health (VHS)", body_style), Paragraph(f"{vhs:.1f} / 100", body_style)],
        [Paragraph("Predicted (+3s)", body_style), Paragraph(f"{pred_v:.2f} V", body_style), Paragraph("Hardware Relay", body_style), Paragraph(f"{'CLOSED (NORMAL)' if fault_flg == 0 else 'TRIPPED (FAULT/OFFLINE)'}", body_style)]
    ]
    
    t_live = Table(live_data, colWidths=[110, 140, 110, 180])
    t_live.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1'))
    ]))
    story.append(t_live)
    story.append(Spacer(1, 4))

    # 3. Aggregated 48-Hour Metrics
    avg_v = float(df["voltage_rms"].mean()) if not df.empty else 0.0
    avg_i = float(df["current_rms"].mean()) if not df.empty else 0.0
    avg_p = float(df["active_power"].mean()) if not df.empty else 0.0
    avg_pf = float(df["power_factor"].mean()) if not df.empty and "power_factor" in df.columns else 0.0
    total_cost = aggregated_kwh * tariff_rate

    story.append(Paragraph("<b>Aggregated 48-Hour Performance & Sustainability Metrics:</b>", heading_style))
    agg_text = f"""
    • <b>Mean Window Voltage:</b> {avg_v:.2f} V (Target 200V-230V) | <b>Mean Current Draw:</b> {avg_i:.2f} A<br/>
    • <b>Average Active Power Load:</b> {avg_p:.1f} W | <b>Mean Power Factor:</b> {avg_pf:.2f}<br/>
    • <b>Total Energy Consumption (48h Projection):</b> {aggregated_kwh:.4f} kWh<br/>
    • <b>Estimated Electricity Cost:</b> ₹{total_cost:.2f} (@ ₹{tariff_rate}/kWh)<br/>
    • <b>Total Carbon Emissions:</b> {aggregated_carbon:.4f} kg CO₂
    """
    story.append(Paragraph(agg_text, body_style))
    story.append(Spacer(1, 4))

    # 4. Comprehensive Multi-Agent System Diagnostics
    story.append(Paragraph("<b>Multi-Agent System Intelligence Engine Responses:</b>", heading_style))
    
    if v_rms == 0:
        fault_agent_msg = "Critical Alert: Hardware disconnected or packet timeout (>15s). Safety interlock engaged."
    elif 200.0 <= v_rms <= 230.0:
        fault_agent_msg = f"Grid stability verified. Voltage operates securely within the 200V-230V envelope. Health Score: {vhs:.1f}/100."
    else:
        fault_agent_msg = f"Critical Voltage Threshold Breach ({v_rms:.1f}V). Hardware relay protection latched."

    energy_agent_msg = f"Active real power draw is {p_act:.1f}W at {i_rms:.2f}A. 48h aggregated projection stands at {aggregated_kwh:.4f} kWh (₹{total_cost:.2f})."

    if pf < 0.90 and pf > 0:
        recom_agent_msg = f"Power Factor Correction Required ({pf:.2f}): Inductive phase lag detected. Integrate shunt capacitor banks."
    elif v_rms < 200.0 and v_rms > 0:
        recom_agent_msg = f"Undervoltage Mitigation ({v_rms:.1f}V): Shed heavy motor loads to avoid coil degradation."
    elif v_rms > 230.0:
        recom_agent_msg = f"Overvoltage Suppression ({v_rms:.1f}V): Upper limit exceeded. Semiconductor interlocks primed."
    else:
        recom_agent_msg = "Optimal power distribution or system offline. No immediate load shedding necessary."

    sust_agent_msg = f"Generated {aggregated_carbon:.4f} kg CO₂ over the active window. Rooftop 3kW peak solar offset potential: ~{(aggregated_kwh * 0.75):.2f} kWh (~{(aggregated_carbon * 0.75):.2f} kg CO₂ reduction)."

    agents_block = f"""
    • <b>Fault Agent Response:</b> {fault_agent_msg}<br/>
    • <b>Energy Agent Response:</b> {energy_agent_msg}<br/>
    • <b>Recommendation Agent Response:</b> {recom_agent_msg}<br/>
    • <b>Sustainability Agent Response:</b> {sust_agent_msg}
    """
    story.append(Paragraph(agents_block, body_style))
    story.append(Spacer(1, 4))

    # 5. Gemini AI Advisor Intelligence Section
    story.append(Paragraph("<b>Gemini Generative AI Intelligence Assessment:</b>", heading_style))
    clean_summary = gemini_summary.replace("**", "").replace("$", "").replace("\\text", "").replace("{", "").replace("}", "")
    for line in clean_summary.split("\n"):
        if line.strip():
            story.append(Paragraph(f"• {line.strip()}", body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer
