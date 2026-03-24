import traci
import numpy as np
from stable_baselines3 import PPO
import csv
import os

# ==========================================
# 0. SETUP THE STREAMLIT BRIDGE
# ==========================================
# Create/Clear the live data file before the simulation starts
with open("live_data.csv", "w", newline='') as f:
    f.write("step,q_j1,q_j7,flow_ew,flow_ns,ambulance_active\n")

def handle_emergency(tls_id):
    """
    Dynamically scans for ambulances and forces the correct green phase.
    Returns True if an emergency was handled, False if the AI should take over.
    """
    # 1. Get all lanes connected to this specific traffic light
    lanes = list(set(traci.trafficlight.getControlledLanes(tls_id)))
    
    for lane in lanes:
        veh_ids = traci.lane.getLastStepVehicleIDs(lane)
        for veh_id in veh_ids:
            # 2. Check if the vehicle is an ambulance
            if traci.vehicle.getVehicleClass(veh_id) == "emergency":
                print(f"🚨 AMBULANCE DETECTED at {tls_id} on lane {lane}! Initiating Green Wave.")
                
                # 3. Dynamically find which phase gives this lane a Green Light
                links = traci.trafficlight.getControlledLinks(tls_id)
                target_link_index = -1
                
                for i, link_group in enumerate(links):
                    if len(link_group) > 0 and link_group[0][0] == lane:
                        target_link_index = i
                        break
                        
                if target_link_index != -1:
                    phases = traci.trafficlight.getCompleteRedYellowGreenDefinition(tls_id)[0].phases
                    for phase_idx, phase in enumerate(phases):
                        # 'G' is a priority green, 'g' is a yielding green
                        if phase.state[target_link_index] in ['G', 'g']:
                            traci.trafficlight.setPhase(tls_id, phase_idx)
                            return True # Emergency handled!
    return False

# ==========================================
# 1. LOAD THE MASTER BRAIN
# ==========================================
print("🧠 Loading AI Brain...")
model = PPO.load("traffic_ai_brain")

# ==========================================
# 2. START THE SIMULATION
# ==========================================
# Make sure this points to your 2-junction config file!
sumo_cmd = ["sumo-gui", "-c", "mysim.sumocfg", "--start"]
traci.start(sumo_cmd)

tls_ids = traci.trafficlight.getIDList()
print(f"🌆 AI taking simultaneous control of: {tls_ids}")

tls_cooldowns = {tls: 0 for tls in tls_ids}

step = 0
while step < 3600:
    traci.simulationStep()
    
    # ------------------------------------------
    # AI DECISION LOOP (Iterates through J1 and J7)
    # ------------------------------------------
    for tls_id in tls_ids:
        # --- 1. EMERGENCY OVERRIDE CHECK ---
        # We check for ambulances EVERY single second, ignoring cooldowns.
        is_emergency = handle_emergency(tls_id)
        
        if is_emergency:
            # Lock the AI out for 3 seconds to let the ambulance pass
            tls_cooldowns[tls_id] = 3 
            continue 

        # --- 2. NORMAL AI OPERATION ---
        if tls_cooldowns[tls_id] > 0:
            tls_cooldowns[tls_id] -= 1
            continue
            
        raw_lanes = traci.trafficlight.getControlledLanes(tls_id)
        
        # Deduplicate lanes while preserving order
        lanes = []
        for lane in raw_lanes:
            if lane not in lanes:
                lanes.append(lane)
        
        observations = []
        for i in range(8):
            if i < len(lanes):
                observations.append(traci.lane.getLastStepHaltingNumber(lanes[i]))
            else:
                observations.append(0) # Failsafe padding
                
        current_phase = traci.trafficlight.getPhase(tls_id)
        observations.append(current_phase)
        state = np.array(observations, dtype=np.float32)
        
        action, _ = model.predict(state, deterministic=True)
        
        if action == 1:
            max_phases = len(traci.trafficlight.getCompleteRedYellowGreenDefinition(tls_id)[0].phases)
            traci.trafficlight.setPhase(tls_id, (current_phase + 1) % max_phases)
            tls_cooldowns[tls_id] = 12 
        else:
            tls_cooldowns[tls_id] = 5 
            
    # ------------------------------------------
    # THE STREAMLIT BRIDGE (Runs every 10 steps)
    # ------------------------------------------
    if step % 10 == 0:
        # Count halted cars on the main incoming edges
        q_j1 = traci.edge.getLastStepHaltingNumber("-E2") + traci.edge.getLastStepHaltingNumber("-E4")
        q_j7 = traci.edge.getLastStepHaltingNumber("E1") + traci.edge.getLastStepHaltingNumber("-E1")
        
        # Count flowing cars (East/West vs North/South)
        flow_ew = traci.edge.getLastStepVehicleNumber("E0") + traci.edge.getLastStepVehicleNumber("-E00")
        flow_ns = traci.edge.getLastStepVehicleNumber("E1.39") + traci.edge.getLastStepVehicleNumber("-E10")
        
        # Check if an ambulance is actively in the network
        amb_active = 1 if any(traci.vehicle.getVehicleClass(veh) == "emergency" for veh in traci.vehicle.getIDList()) else 0
        
        # Write to the CSV file so the website can read it
        with open("live_data.csv", "a", newline='') as f:
            f.write(f"{step},{q_j1},{q_j7},{flow_ew},{flow_ns},{amb_active}\n")
            
    step += 1

traci.close()
print("✅ Corridor Simulation Complete!")