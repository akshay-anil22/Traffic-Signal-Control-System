import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import os
import base64
from datetime import datetime

def get_image_base64(image_path):
    """Converts a local image into a base64 string for HTML embedding."""
    try:
        with open(image_path, "rb") as img_file:
            encoded_string = base64.b64encode(img_file.read()).decode()
            return f"data:image/png;base64,{encoded_string}"
    except Exception as e:
        return "" # Returns empty if the file isn't found

# ==========================================
# 1. PAGE CONFIGURATION & CSS
# ==========================================
st.set_page_config(page_title="Smart City Command Center", page_icon="🚦", layout="wide")

st.markdown("""
    <style>
    .main {background-color: #0E1117;}
    h1, h2, h3, h4 {color: #E2E8F0; font-family: 'Inter', sans-serif;}
    
    /* --- FIX 3: REMOVE HEADING ANCHOR LINKS --- */
    .header-anchor, h1 a, h2 a, h3 a, h4 a {
        display: none !important;
    }
    
    .metric-card {
        background-color: #1A202C; 
        border-radius: 12px; 
        padding: 15px; 
        border: 1px solid #2D3748; 
        margin-bottom: 10px;
        height: 110px; 
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .metric-title {
        color: #E2E8F0; 
        font-size: 12px; 
        margin-bottom: 5px; 
        opacity: 0.8;
        white-space: nowrap; 
    }
    .metric-value {
        font-size: 26px; 
        font-weight: bold; 
        margin: 0;
    }
    </style>
""", unsafe_allow_html=True)

# Theme Colors
BG_COLOR, CARD_COLOR, TEXT_COLOR, AXIS_COLOR = "#0E1117", "#1A202C", "#E2E8F0", "#A0AEC0"
GREEN, PURPLE, CORAL, CYAN = "#00FF41", "#C179E0", "#FCA5A5", "#0BC5EA" 

# ==========================================
# 2. DATA PIPELINE
# ==========================================
DATA_FILE = "live_data.csv"
HISTORY_FILE = "episode_summary.csv"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            df = pd.read_csv(DATA_FILE)
            if len(df) > 0:
                return df.tail(60) 
        except:
            pass
    return pd.DataFrame({"step": [0], "q_j1": [0], "q_j7": [0], "flow_ew": [0], "flow_ns": [0], "ambulance_active": [0]})

def get_average_co2():
    if os.path.exists(HISTORY_FILE):
        try:
            df_hist = pd.read_csv(HISTORY_FILE)
            if len(df_hist) > 0:
                return df_hist['co2_kg'].mean() 
        except:
            pass
    return 0.0

df = load_data()
latest = df.iloc[-1]
current_step = int(latest['step'])
total_queue = int(latest['q_j1'] + latest['q_j7'])
total_flow = int(latest['flow_ew'] + latest['flow_ns'])
emergency_status = "ACTIVE 🚑" if latest['ambulance_active'] == 1 else "STANDBY"
emergency_color = CORAL if latest['ambulance_active'] == 1 else "#A0AEC0"
avg_co2 = get_average_co2()

# ==========================================
# 3. HEADER & LOGOS
# ==========================================
# We only need 2 columns now: One for the Title block, one for the Time.
col_title, col_time = st.columns([4, 1])

with col_title:
    # Using Flexbox to lock the image and the text perfectly together side-by-side
    st.markdown("""
        <div style="display: flex; align-items: center; gap: 35px;">
            <img src="https://cdn-icons-png.flaticon.com/512/2000/2000887.png" width="60">
            <div>
                <h1 style="margin: 0px; padding: 0px;">Smart City Command Center</h1>
                <h4 style="margin: 0px; padding-top: 5px; color: #A0AEC0;">Decentralized PPO Traffic System</h4>
            </div>
        </div>
    """, unsafe_allow_html=True)

with col_time:
    st.markdown(f"<div style='text-align: right; color: {GREEN}; font-family: monospace; font-size: 18px;'><br>SYS.TIME: {current_step}s</div>", unsafe_allow_html=True)

st.markdown("---")

# ==========================================
# 4. ROW 1: METRIC CARDS 
# ==========================================
met1, met2, met3, met4, met5 = st.columns(5)

met1.markdown(f'<div class="metric-card"><p class="metric-title">SIMULATION TIME</p><p class="metric-value" style="color:{TEXT_COLOR}">{current_step}s</p></div>', unsafe_allow_html=True)
met2.markdown(f'<div class="metric-card"><p class="metric-title">TOTAL STOPPED CARS</p><p class="metric-value" style="color:{PURPLE}">{total_queue}</p></div>', unsafe_allow_html=True)
met3.markdown(f'<div class="metric-card"><p class="metric-title">ACTIVE FLOW (VEH/S)</p><p class="metric-value" style="color:{GREEN}">{total_flow}</p></div>', unsafe_allow_html=True)
met4.markdown(f'<div class="metric-card"><p class="metric-title">EMERGENCY OVERRIDE</p><p class="metric-value" style="color:{emergency_color};">{emergency_status}</p></div>', unsafe_allow_html=True)
met5.markdown(f'<div class="metric-card"><p class="metric-title">AVG CO2 (PAST RUNS)</p><p class="metric-value" style="color:{CYAN}">{avg_co2:.2f} kg</p></div>', unsafe_allow_html=True)

# --- FIX 1: ADDED VERTICAL SPACING ---
st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# 5. ROW 2: LARGE CHARTS
# ==========================================
chart_col1, chart_col2 = st.columns(2, gap="large")

with chart_col1:
    st.markdown("#### Live Queue Lengths (J1 vs J7)")
    fig_q = px.area(df, x='step', y=['q_j1', 'q_j7'], 
                    color_discrete_map={"q_j1": PURPLE, "q_j7": GREEN},
                    labels={"value": "Stopped Cars", "step": "Time (s)", "variable": "Junction"})
    
    fig_q.update_layout(height=260, paper_bgcolor=BG_COLOR, plot_bgcolor=BG_COLOR, font_color=TEXT_COLOR,
                        xaxis=dict(showgrid=False), yaxis=dict(gridcolor=AXIS_COLOR),
                        margin=dict(l=0, r=0, b=0, t=20), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig_q, use_container_width=True)

with chart_col2:
    st.markdown("#### Directional Throughput")
    fig_flow = go.Figure()
    fig_flow.add_trace(go.Bar(name='East-West Flow', x=df['step'], y=df['flow_ew'], marker_color=GREEN))
    fig_flow.add_trace(go.Bar(name='North-South Flow', x=df['step'], y=df['flow_ns'], marker_color=PURPLE))

    fig_flow.update_layout(height=260, barmode='group', paper_bgcolor=BG_COLOR, plot_bgcolor=BG_COLOR, font_color=TEXT_COLOR,
                           margin=dict(l=0, r=0, b=0, t=20), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig_flow, use_container_width=True)

# --- FIX 1: ADDED VERTICAL SPACING ---
st.markdown("<br><br><br><br>", unsafe_allow_html=True)

# ==========================================
# 6. ROW 3: DONUT & EMERGENCY CHARTS
# ==========================================
chart_col3, chart_col4 = st.columns(2, gap="large")

with chart_col3:
    st.markdown("#### Clearance Ratio (Last 60s)")
    total_ew_cleared = df['flow_ew'].sum()
    total_ns_cleared = df['flow_ns'].sum()
    
    if total_ew_cleared == 0 and total_ns_cleared == 0:
        total_ew_cleared, total_ns_cleared = 1, 1 

    fig_phase = px.pie(values=[total_ew_cleared, total_ns_cleared], names=['East-West', 'North-South'], 
                       hole=.75, color_discrete_sequence=[GREEN, PURPLE])
    fig_phase.update_traces(textinfo='none')
    fig_phase.add_annotation(text="FLOW", x=0.5, y=0.5, showarrow=False, font=dict(size=24, color=TEXT_COLOR))
    
    fig_phase.update_layout(height=260, paper_bgcolor=BG_COLOR, plot_bgcolor=BG_COLOR, font_color=TEXT_COLOR, margin=dict(l=0, r=0, b=0, t=20), legend=dict(orientation="h", yanchor="bottom", y=0.02, xanchor="left", x=0))
    st.plotly_chart(fig_phase, use_container_width=True)

with chart_col4:
    st.markdown("#### Ambulance Priority Triggers")
    fig_emerg = px.line(df, x='step', y='ambulance_active', line_shape='hv')
    fig_emerg.update_traces(line_color=CORAL, fill='tozeroy', fillcolor='rgba(252, 165, 165, 0.2)')
    
    fig_emerg.update_layout(height=260, paper_bgcolor=BG_COLOR, plot_bgcolor=BG_COLOR, font_color=TEXT_COLOR,
                            yaxis=dict(tickvals=[0, 1], ticktext=['Standby', 'Override Active']),
                            margin=dict(l=0, r=0, b=0, t=20))
    st.plotly_chart(fig_emerg, use_container_width=True)

# ==========================================
# 7. FOOTER LOGOS
# ==========================================
st.markdown("---")
st.markdown("<p style='text-align: center; color: #A0AEC0; font-size: 12px;'>POWERED BY</p>", unsafe_allow_html=True)

# 1. Convert your local file to base64 first
fb_logo = get_image_base64("./assets/image-facebook-removebg-preview.png")

# 2. Put all three images inside a single CSS Flexbox container!
#    'gap: 40px' controls the exact distance between the logos.
#    'align-items: center' ensures they all line up perfectly on the horizontal axis.
st.markdown(f"""
    <div style="display: flex; justify-content: center; align-items: center; gap: 40px;">
        <img src="https://upload.wikimedia.org/wikipedia/commons/c/c3/Python-logo-notext.svg" width="40">
        <img src="{fb_logo}" width="80">
        <img src="https://streamlit.io/images/brand/streamlit-mark-color.svg" width="50">
    </div>
""", unsafe_allow_html=True)

# ==========================================
# 8. AUTO-REFRESH LOOP
# ==========================================
time.sleep(2)
st.rerun()