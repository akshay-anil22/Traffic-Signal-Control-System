import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import os
from datetime import datetime

# ==========================================
# 1. PAGE CONFIGURATION & CSS
# ==========================================
st.set_page_config(page_title="Smart City Command Center", page_icon="🚦", layout="wide")

st.markdown("""
    <style>
    .main {background-color: #0E1117;}
    h1, h2, h3, h4 {color: #E2E8F0; font-family: 'Inter', sans-serif;}
    .metric-card {background-color: #1A202C; border-radius: 12px; padding: 20px; border: 1px solid #2D3748; margin-bottom: 10px;}
    .metric-title {color: #E2E8F0; font-size: 14px; margin-bottom: 5px; opacity: 0.8;}
    .metric-value {color: #00FF41; font-size: 32px; font-weight: bold; margin: 0;}
    </style>
""", unsafe_allow_html=True)

# Theme Colors
BG_COLOR, CARD_COLOR, TEXT_COLOR, AXIS_COLOR = "#0E1117", "#1A202C", "#E2E8F0", "#A0AEC0"
GREEN, PURPLE, CORAL = "#00FF41", "#C179E0", "#FCA5A5"

# ==========================================
# 2. DATA PIPELINE (The Bridge)
# ==========================================
DATA_FILE = "live_data.csv"

# Function to safely load data
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            df = pd.read_csv(DATA_FILE)
            if len(df) > 0:
                # Only keep the last 60 data points so the chart moves like a heartbeat monitor
                return df.tail(60) 
        except:
            pass
    # If simulation isn't running yet, return empty skeleton
    return pd.DataFrame({"step": [0], "q_j1": [0], "q_j7": [0], "flow_ew": [0], "flow_ns": [0], "ambulance_active": [0]})

df = load_data()

# Extract latest metrics for the cards
latest = df.iloc[-1]
current_step = int(latest['step'])
total_queue = int(latest['q_j1'] + latest['q_j7'])
total_flow = int(latest['flow_ew'] + latest['flow_ns'])
emergency_status = "ACTIVE 🚑" if latest['ambulance_active'] == 1 else "STANDBY"
emergency_color = CORAL if latest['ambulance_active'] == 1 else "#A0AEC0"

# ==========================================
# 3. HEADER & LOGOS
# ==========================================
# Header with a tech logo
col_logo, col_text, col_time = st.columns([1, 6, 2])
with col_logo:
    st.image("https://cdn-icons-png.flaticon.com/512/2000/2000887.png", width=70) # AI Brain Icon
with col_text:
    st.markdown("<h1 style='margin-bottom: 0px;'>Smart City Command Center</h1>", unsafe_allow_html=True)
    st.markdown("### Decentralized PPO Traffic System")
with col_time:
    st.markdown(f"<div style='text-align: right; color: {GREEN}; font-family: monospace; font-size: 18px;'><br>SYS.TIME: {current_step}s</div>", unsafe_allow_html=True)

st.markdown("---")

# ==========================================
# 4. ROW 1: METRIC CARDS
# ==========================================
met1, met2, met3, met4 = st.columns(4)

met1.markdown(f'<div class="metric-card"><p class="metric-title">SIMULATION TIME</p><p class="metric-value" style="color:{TEXT_COLOR}">{current_step}s</p></div>', unsafe_allow_html=True)
met2.markdown(f'<div class="metric-card"><p class="metric-title">TOTAL STOPPED CARS</p><p class="metric-value" style="color:{PURPLE}">{total_queue}</p></div>', unsafe_allow_html=True)
met3.markdown(f'<div class="metric-card"><p class="metric-title">ACTIVE FLOW (VEH/S)</p><p class="metric-value" style="color:{GREEN}">{total_flow}</p></div>', unsafe_allow_html=True)
met4.markdown(f'<div class="metric-card"><p class="metric-title">EMERGENCY OVERRIDE</p><p class="metric-value" style="color:{emergency_color}; font-size: 24px; margin-top: 8px;">{emergency_status}</p></div>', unsafe_allow_html=True)

# ==========================================
# 5. ROW 2: LARGE CHARTS 
# ==========================================
row1_col1, row1_col2 = st.columns([2, 1.5])

# Chart 1: Queue Area Chart (Shows Traffic Jams)
with row1_col1:
    st.markdown("#### Live Queue Lengths (J1 vs J7)")
    fig_q = px.area(df, x='step', y=['q_j1', 'q_j7'], 
                    color_discrete_map={"q_j1": PURPLE, "q_j7": GREEN},
                    labels={"value": "Stopped Cars", "step": "Time (s)", "variable": "Junction"})
    
    fig_q.update_layout(paper_bgcolor=BG_COLOR, plot_bgcolor=BG_COLOR, font_color=TEXT_COLOR,
                        xaxis=dict(showgrid=False), yaxis=dict(gridcolor=AXIS_COLOR),
                        margin=dict(l=0, r=0, b=0, t=20), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig_q, use_container_width=True)

# Chart 2: Grouped Bar Chart (Directional Flow)
with row1_col2:
    st.markdown("#### Directional Throughput")
    fig_flow = go.Figure()
    fig_flow.add_trace(go.Bar(name='East-West Flow', x=df['step'], y=df['flow_ew'], marker_color=GREEN))
    fig_flow.add_trace(go.Bar(name='North-South Flow', x=df['step'], y=df['flow_ns'], marker_color=PURPLE))

    fig_flow.update_layout(barmode='group', paper_bgcolor=BG_COLOR, plot_bgcolor=BG_COLOR, font_color=TEXT_COLOR,
                           margin=dict(l=0, r=0, b=0, t=20), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig_flow, use_container_width=True)

# ==========================================
# 6. ROW 3: DONUT & EMERGENCY CHARTS
# ==========================================
row2_col1, row2_col2 = st.columns([1, 2])

# Chart 3: Donut Chart (Total Clearance Ratio)
with row2_col1:
    st.markdown("#### Clearance Ratio (Last 60s)")
    total_ew_cleared = df['flow_ew'].sum()
    total_ns_cleared = df['flow_ns'].sum()
    
    # Prevent division by zero if simulation just started
    if total_ew_cleared == 0 and total_ns_cleared == 0:
        total_ew_cleared, total_ns_cleared = 1, 1 

    fig_phase = px.pie(values=[total_ew_cleared, total_ns_cleared], names=['East-West', 'North-South'], 
                       hole=.75, color_discrete_sequence=[GREEN, PURPLE])
    fig_phase.update_traces(textinfo='none')
    fig_phase.add_annotation(text="FLOW", x=0.5, y=0.5, showarrow=False, font=dict(size=24, color=TEXT_COLOR))
    fig_phase.update_layout(paper_bgcolor=BG_COLOR, plot_bgcolor=BG_COLOR, font_color=TEXT_COLOR, margin=dict(l=0, r=0, b=0, t=20), legend=dict(orientation="h", yanchor="bottom", y=0.02, xanchor="left", x=0))
    st.plotly_chart(fig_phase, use_container_width=True)

# Chart 4: Stepped Line Chart (Emergency Override Triggers)
with row2_col2:
    st.markdown("#### Ambulance Priority Triggers")
    fig_emerg = px.line(df, x='step', y='ambulance_active', line_shape='hv') # 'hv' makes it a step chart!
    fig_emerg.update_traces(line_color=CORAL, fill='tozeroy', fillcolor='rgba(252, 165, 165, 0.2)')
    fig_emerg.update_layout(paper_bgcolor=BG_COLOR, plot_bgcolor=BG_COLOR, font_color=TEXT_COLOR,
                            yaxis=dict(tickvals=[0, 1], ticktext=['Standby', 'Override Active']),
                            margin=dict(l=0, r=0, b=0, t=20))
    st.plotly_chart(fig_emerg, use_container_width=True)

# ==========================================
# 7. FOOTER LOGOS
# ==========================================
st.markdown("---")
st.markdown("<p style='text-align: center; color: #A0AEC0; font-size: 12px;'>POWERED BY</p>", unsafe_allow_html=True)
footer_col1, footer_col2, footer_col3, footer_col4, footer_col5 = st.columns([2, 1, 1, 1, 2])
with footer_col2:
    st.image("https://upload.wikimedia.org/wikipedia/commons/c/c3/Python-logo-notext.svg", width=40)
with footer_col3:
    st.image("https://eclipse.dev/sumo/images/sumo-logo.png", width=80)
with footer_col4:
    st.image("https://streamlit.io/images/brand/streamlit-mark-color.svg", width=50)

# ==========================================
# 8. AUTO-REFRESH LOOP
# ==========================================
# This pauses the website for 2 seconds, then re-runs it to fetch new data!
time.sleep(2)
st.rerun()