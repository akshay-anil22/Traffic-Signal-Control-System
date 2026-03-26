import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import os
import base64

def get_image_base64(image_path):
    try:
        with open(image_path, "rb") as img_file:
            encoded_string = base64.b64encode(img_file.read()).decode()
            return f"data:image/png;base64,{encoded_string}"
    except Exception as e:
        return "" 

# ==========================================
# 0. SESSION STATE INITIALIZATION
# ==========================================
if 'fleet_idx' not in st.session_state:
    st.session_state.fleet_idx = 0

def next_fleet(): st.session_state.fleet_idx = (st.session_state.fleet_idx + 1) % 5
def prev_fleet(): st.session_state.fleet_idx = (st.session_state.fleet_idx - 1) % 5

# ==========================================
# 1. PAGE CONFIGURATION & NEON CYBERPUNK CSS
# ==========================================
st.set_page_config(page_title="Smart City Command Center", page_icon="🚦", layout="wide")

st.markdown("""
    <style>
    /* Pure Black Background */
    .stApp { background-color: #000000; color: #FFFFFF; }
    h1, h2, h3, h4, p {color: #FFFFFF; font-family: 'Inter', sans-serif;}
    .header-anchor, h1 a, h2 a, h3 a, h4 a { display: none !important; }
    
    /* Neon Dark Cards */
    .dark-card, .white-card { 
        background-color: #050505; 
        border-radius: 15px; 
        padding: 20px; 
        border: 1px solid #1A1A1A; 
        box-shadow: 0 0 15px rgba(0, 208, 255, 0.05); /* Faint blue ambient glow */
        margin-bottom: 20px;
    }
    
    /* Small Metric Cards with Neon Red Accent */
    .small-card { 
        background-color: #050505; 
        border-radius: 12px; 
        padding: 15px; 
        border: 1px solid #1A1A1A; 
        margin-bottom: 12px; 
        border-left: 4px solid #FF003C; /* Neon Red */
        box-shadow: 0 0 10px rgba(255, 0, 60, 0.15); /* Red Glow */
    }
    
    .metric-title { font-size: 13px; color: #888888; margin-bottom: 5px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px;}
    .metric-value { font-size: 24px; font-weight: bold; margin: 0; color: #FFFFFF; text-shadow: 0 0 5px rgba(255,255,255,0.3);}
    
    /* Neon Blue Glowing Buttons */
    div[data-testid="column"]:nth-of-type(1) div.stButton > button, 
    div[data-testid="column"]:nth-of-type(3) div.stButton > button {
        background-color: transparent !important;
        color: #00D0FF !important; /* Neon Blue */
        border-radius: 8px !important;
        border: 2px solid #00D0FF !important;
        height: 50px !important;
        box-shadow: 0 0 15px rgba(0, 208, 255, 0.3) !important;
        transition: all 0.2s ease-in-out !important;
    }
    
    div[data-testid="column"]:nth-of-type(1) div.stButton > button *, 
    div[data-testid="column"]:nth-of-type(3) div.stButton > button * {
        color: #00D0FF !important;
        font-size: 20px !important;
        font-weight: bold !important;
    }
    
    /* Button Hover Effect - Solid Glow */
    div[data-testid="column"]:nth-of-type(1) div.stButton > button:hover,
    div[data-testid="column"]:nth-of-type(3) div.stButton > button:hover {
        background-color: #00D0FF !important;
        box-shadow: 0 0 25px rgba(0, 208, 255, 0.6) !important;
        transform: scale(1.02) !important;
    }
    
    div[data-testid="column"]:nth-of-type(1) div.stButton > button:hover *, 
    div[data-testid="column"]:nth-of-type(3) div.stButton > button:hover * {
        color: #000000 !important; /* Text turns black when hovered */
    }
    </style>
""", unsafe_allow_html=True)

# Pure Black Theme Colors for Graphs
BG_COLOR, TEXT_COLOR, AXIS_COLOR = "#000000", "#FFFFFF", "#222222"

# Hijacking the old color names to output Neon Red and Neon Blue
GREEN = "#00D0FF"   # Now renders as Neon Blue
PURPLE = "#FF003C"  # Now renders as Neon Red
CORAL = "#FF003C"   # Now renders as Neon Red
CYAN = "#00D0FF"    # Now renders as Neon Blue

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
                return df.fillna(0) 
        except:
            pass
    return pd.DataFrame({
        "step": [0], "q_j1": [0], "q_j7": [0], "flow_ew": [0], "flow_ns": [0], 
        "ambulance_active": [0], "co2_j1": [0.0], "co2_j7": [0.0],
        "cars_j1": [0], "cars_j7": [0], "tot_car": [0], "tot_amb": [0], "tot_bus": [0], "tot_ped": [0], "tot_truck": [0]
    })

def get_average_co2():
    if os.path.exists(HISTORY_FILE):
        try:
            df_hist = pd.read_csv(HISTORY_FILE)
            if len(df_hist) > 0: return df_hist['co2_kg'].mean() 
        except: pass
    return 0.0

df = load_data()
latest = df.iloc[-1]
avg_co2 = get_average_co2()

current_step = int(latest.get('step', 0))
total_emergencies = int(df['ambulance_active'].sum() / 10) 
total_cleared = int(latest.get('flow_ew', 0) + latest.get('flow_ns', 0))

# ==========================================
# 3. HEADER
# ==========================================
col_title, col_time = st.columns([4, 1])
with col_title:
    st.markdown("""
        <div style="display: flex; align-items: center; gap: 20px; margin-bottom: 20px;">
            <div style="background-color: #050505; padding: 10px; border-radius: 10px; border: 1px solid #1A1A1A;">
                <h2 style="margin: 0px; color: white;">🚦</h2>
            </div>
            <div>
                <h2 style="margin: 0px; padding: 0px; color: #FFFFFF; text-shadow: 0 0 10px rgba(0,208,255,0.3);">Traffic Analytics Dashboard</h2>
                <p style="margin: 0px; color: #888888;">Live System Monitoring</p>
            </div>
        </div>
    """, unsafe_allow_html=True)


# ==========================================
# 4. MIDDLE ROW: METRICS & INTERACTIVE FLEET WIDGET
# ==========================================
col_left, col_right = st.columns([1, 2])

with col_left:
    st.markdown("#### System Metrics")
    st.markdown(f'<div class="small-card"><p class="metric-title">TOTAL SIMULATION TIME</p><p class="metric-value">{current_step} sec</p></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="small-card" style="border-left: 4px solid {CORAL}; box-shadow: 0 0 10px rgba(255, 0, 60, 0.15);"><p class="metric-title">EMERGENCY TRIGGERS</p><p class="metric-value">{total_emergencies}</p></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="small-card" style="border-left: 4px solid {CYAN}; box-shadow: 0 0 10px rgba(0, 208, 255, 0.15);"><p class="metric-title">AVG CO2 (PAST RUNS)</p><p class="metric-value" style="color:{CYAN};">{avg_co2:.2f} kg</p></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="small-card" style="border-left: 4px solid {PURPLE}; box-shadow: 0 0 10px rgba(255, 0, 60, 0.15);"><p class="metric-title">LIVE CO2 (J1)</p><p class="metric-value">{latest.get("co2_j1", 0):.2f} mg</p><p style="margin:0; font-size:11px; color:#888888;">Caused by {int(latest.get("cars_j1", 0))} cars</p></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="small-card" style="border-left: 4px solid {PURPLE}; box-shadow: 0 0 10px rgba(255, 0, 60, 0.15);"><p class="metric-title">LIVE CO2 (J7)</p><p class="metric-value">{latest.get("co2_j7", 0):.2f} mg</p><p style="margin:0; font-size:11px; color:#888888;">Caused by {int(latest.get("cars_j7", 0))} cars</p></div>', unsafe_allow_html=True)

with col_right:
    st.markdown("#### Cumulative Entity Log")
    
    fleet_data = [
        {"name": "Passenger Cars", "icon": "🚗", "short": "Car", "count": int(latest.get('tot_car', 0))},
        {"name": "Ambulances", "icon": "🚑", "short": "Ambulance", "count": int(latest.get('tot_amb', 0))},
        {"name": "Cargo Trucks", "icon": "🚚", "short": "Truck", "count": int(latest.get('tot_truck', 0))},
        {"name": "Heavy Buses", "icon": "🚌", "short": "Bus", "count": int(latest.get('tot_bus', 0))},
        {"name": "Pedestrians", "icon": "🚶", "short": "Pedestrian", "count": int(latest.get('tot_ped', 0))}
    ]
    
    idx = st.session_state.fleet_idx
    curr = fleet_data[idx]
    prev_idx = (idx - 1) % 5
    next_idx = (idx + 1) % 5
    
    html_card = f"""
    <div class="dark-card" style="display: flex; flex-direction: column; align-items: center; padding-bottom: 20px; height: 400px;">
        <h3 style='text-align: center; color: #888888; margin-top: 0;'>{curr['name']} Processed</h3>
        <div style='font-size: 140px; line-height: 1.2; text-align: center;'>{curr['icon']}</div>
        <h1 style='text-align: center; font-size: 70px; margin: 0; padding: 0; color: #FFFFFF; text-shadow: 0 0 10px rgba(255,255,255,0.3);'>{curr['count']}</h1>
        <p style='text-align: center; font-weight: bold; color: #888888; letter-spacing: 1px; margin-bottom: 10px;'>TOTAL CUMULATIVE COUNT</p>
    </div>
    """
    st.markdown(html_card, unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c1:
        st.button(f"❮", on_click=prev_fleet, key="prev", use_container_width=True)
    with c3:
        st.button(f"❯", on_click=next_fleet, key="next", use_container_width=True)
        
# ==========================================
# 5. BOTTOM ROW: FULL GRAPHS
# ==========================================
st.markdown("#### Network Flow History")


st.markdown("<h5 style='color: #888888;'>Live Queue Lengths (J1 vs J7)</h5>", unsafe_allow_html=True)
fig_q = px.line(df, x='step', y=['q_j1', 'q_j7'], color_discrete_map={"q_j1": PURPLE, "q_j7": GREEN})
fig_q.update_layout(height=250, paper_bgcolor=BG_COLOR, plot_bgcolor=BG_COLOR, margin=dict(l=0, r=0, b=0, t=10), xaxis=dict(showgrid=True, gridcolor=AXIS_COLOR, title=""), yaxis=dict(showgrid=True, gridcolor=AXIS_COLOR))
st.plotly_chart(fig_q, use_container_width=True)

st.markdown(f"<hr style='border: 1px solid {AXIS_COLOR};'>", unsafe_allow_html=True)

st.markdown("<h5 style='color: #888888;'>Directional Throughput</h5>", unsafe_allow_html=True)
fig_flow = go.Figure()
fig_flow.add_trace(go.Bar(name='East-West Flow', x=df['step'], y=df['flow_ew'], marker_color=GREEN))
fig_flow.add_trace(go.Bar(name='North-South Flow', x=df['step'], y=df['flow_ns'], marker_color=PURPLE))
fig_flow.update_layout(height=250, barmode='group', paper_bgcolor=BG_COLOR, plot_bgcolor=BG_COLOR, margin=dict(l=0, r=0, b=0, t=10), xaxis=dict(showgrid=True, gridcolor=AXIS_COLOR), yaxis=dict(showgrid=True, gridcolor=AXIS_COLOR))
st.plotly_chart(fig_flow, use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 6. FOOTER LOGOS
# ==========================================
st.markdown("---")
st.markdown("<p style='text-align: center; color: #888888; font-size: 12px; font-weight: bold;'>POWERED BY</p>", unsafe_allow_html=True)

fb_logo = get_image_base64("./assets/image-facebook-removebg-preview.png")

st.markdown(f"""
    <div style="display: flex; justify-content: center; align-items: center; gap: 40px; margin-bottom: 30px;">
        <img src="https://upload.wikimedia.org/wikipedia/commons/c/c3/Python-logo-notext.svg" width="40" style="filter: drop-shadow(0px 0px 5px rgba(255,255,255,0.3));">
        <img src="{fb_logo}" width="80" style="filter: drop-shadow(0px 0px 5px rgba(255,255,255,0.3));">
        <img src="https://streamlit.io/images/brand/streamlit-mark-color.svg" width="50" style="filter: drop-shadow(0px 0px 5px rgba(255,255,255,0.3));">
    </div>
""", unsafe_allow_html=True)

time.sleep(2)
st.rerun()