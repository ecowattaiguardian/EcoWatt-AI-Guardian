import plotly.graph_objects as go
import pandas as pd

def create_voltage_chart(df: pd.DataFrame) -> go.Figure:
    """
    Generates a dark-themed Plotly line chart for Voltage vs Time with 200V-230V safety limit lines.
    """
    fig = go.Figure()

    if not df.empty:
        # Support both 'voltage' and 'voltage_rms' column naming conventions
        v_col = "voltage" if "voltage" in df.columns else ("voltage_rms" if "voltage_rms" in df.columns else None)
        t_col = "timestamp" if "timestamp" in df.columns else None

        if v_col and t_col:
            fig.add_trace(go.Scatter(
                x=df[t_col],
                y=df[v_col],
                mode='lines+markers',
                name='RMS Voltage (V)',
                line=dict(color='#00E5FF', width=2),
                marker=dict(size=5)
            ))

    # Add Upper & Lower Safety Boundaries for 200V - 230V Window
    fig.add_hline(y=230, line_dash="dash", line_color="#FF1744", annotation_text="Over-Voltage Limit (230V)")
    fig.add_hline(y=200, line_dash="dash", line_color="#FF1744", annotation_text="Under-Voltage Limit (200V)")
    fig.add_hline(y=215, line_dash="dot", line_color="#00E676", annotation_text="Nominal Midpoint (215V)")

    fig.update_layout(
        title="📈 Real-Time Voltage Stream (V)",
        xaxis_title="Timestamp",
        yaxis_title="Voltage (V)",
        template="plotly_dark",
        height=350,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    return fig

def create_power_chart(df: pd.DataFrame) -> go.Figure:
    """
    Generates a Plotly area chart for Power Draw (W) over time.
    """
    fig = go.Figure()

    if not df.empty:
        # Support both 'power' and 'active_power' column naming conventions
        p_col = "power" if "power" in df.columns else ("active_power" if "active_power" in df.columns else None)
        t_col = "timestamp" if "timestamp" in df.columns else None

        if p_col and t_col:
            fig.add_trace(go.Scatter(
                x=df[t_col],
                y=df[p_col],
                mode='lines',
                fill='tozeroy',
                name='Active Power (W)',
                line=dict(color='#7C4DFF', width=2),
                fillcolor='rgba(124, 77, 255, 0.2)'
            ))

    fig.update_layout(
        title="⚡ Active Power Draw (W)",
        xaxis_title="Timestamp",
        yaxis_title="Power (W)",
        template="plotly_dark",
        height=350,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    return fig