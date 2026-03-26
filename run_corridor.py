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
    f.write("step,q_j1,q_j7,flow_ew,flow_ns,ambulance_active,co2_j1,co2_j7,cars_j1,cars_j7,tot_car,tot_amb,tot_bus,tot_ped,tot_truck\n")

def handle_emergency(tls_id):
    lanes = list(set(traci.trafficlight.getControlledLanes(tls_id)))
    for lane in lanes:
        veh_ids = traci.lane.getLastStepVehicleIDs(lane)
        for veh_id in veh_ids:
            if traci.vehicle.getVehicleClass(veh_id) == "emergency":
                print(f"🚨 AMBULANCE DETECTED at {tls_id} on lane {lane}! Initiating Green Wave.")
                links = traci.trafficlight.getControlledLinks(tls_id)
                target_link_index = -1
                for i, link_group in enumerate(links):
                    if len(link_group) > 0 and link_group[0][0] == lane:
                        target_link_index = i
                        break
                if target_link_index != -1:
                    phases = traci.trafficlight.getCompleteRedYellowGreenDefinition(tls_id)[0].phases
                    for phase_idx, phase in enumerate(phases):
                        if phase.state[target_link_index] in ['G', 'g']:
                            traci.trafficlight.setPhase(tls_id, phase_idx)
                            return True 
    return False

# ==========================================
# 1. LOAD THE MASTER BRAIN
# ==========================================
print("🧠 Loading AI Brain...")
model = PPO.load("traffic_ai_brain")

# ==========================================
# 2. START THE SIMULATION
# ==========================================
sumo_cmd = ["sumo-gui", "-c", "mysim.sumocfg", "--start"]
traci.start(sumo_cmd)
tls_ids = traci.trafficlight.getIDList()
print(f"🌆 AI taking simultaneous control of: {tls_ids}")

tls_cooldowns = {tls: 0 for tls in tls_ids}

# --- MEMORY SETS FOR CUMULATIVE COUNTING ---
seen_cars = set()
seen_ambs = set()
seen_buses = set()
seen_trucks = set()
seen_peds = set()

step = 0
while step < 3600:
    traci.simulationStep()
    
    # ------------------------------------------
    # AI DECISION LOOP
    # ------------------------------------------
    for tls_id in tls_ids:
        is_emergency = handle_emergency(tls_id)
        if is_emergency:
            tls_cooldowns[tls_id] = 3 
            continue 

        if tls_cooldowns[tls_id] > 0:
            tls_cooldowns[tls_id] -= 1
            continue
            
        raw_lanes = traci.trafficlight.getControlledLanes(tls_id)
        lanes = []
        for lane in raw_lanes:
            if lane not in lanes:
                lanes.append(lane)
        
        observations = []
        for i in range(8):
            if i < len(lanes):
                observations.append(traci.lane.getLastStepHaltingNumber(lanes[i]))
            else:
                observations.append(0) 
                
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
    # TRACK CUMULATIVE TOTALS (Runs every second)
    # ------------------------------------------
    all_vehs = traci.vehicle.getIDList()
    amb_active = 0
    
    for v in all_vehs:
        v_class = traci.vehicle.getVehicleClass(v)
        if v_class == "passenger": seen_cars.add(v)
        elif v_class == "emergency": 
            seen_ambs.add(v)
            amb_active = 1 # Keep this to trigger the chart!
        elif v_class == "bus": seen_buses.add(v)
        elif v_class == "truck": seen_trucks.add(v)
        
    for p in traci.person.getIDList():
        seen_peds.add(p)

    # ------------------------------------------
    # THE STREAMLIT BRIDGE (Runs every 10 steps)
    # ------------------------------------------
    if step % 10 == 0:
        q_j1 = traci.edge.getLastStepHaltingNumber("-E2") + traci.edge.getLastStepHaltingNumber("-E4")
        q_j7 = traci.edge.getLastStepHaltingNumber("E1") + traci.edge.getLastStepHaltingNumber("-E1")
        
        flow_ew = traci.edge.getLastStepVehicleNumber("E0") + traci.edge.getLastStepVehicleNumber("-E00")
        flow_ns = traci.edge.getLastStepVehicleNumber("E1.39") + traci.edge.getLastStepVehicleNumber("-E10")
        
        co2_j1 = traci.edge.getCO2Emission("-E2") + traci.edge.getCO2Emission("-E4")
        co2_j7 = traci.edge.getCO2Emission("E1") + traci.edge.getCO2Emission("-E1")
        
        cars_j1 = traci.edge.getLastStepVehicleNumber("-E2") + traci.edge.getLastStepVehicleNumber("-E4")
        cars_j7 = traci.edge.getLastStepVehicleNumber("E1") + traci.edge.getLastStepVehicleNumber("-E1")
        
        # Get the length of our memory sets!
        t_car = len(seen_cars)
        t_amb = len(seen_ambs)
        t_bus = len(seen_buses)
        t_ped = len(seen_peds)
        t_truck = len(seen_trucks)

        with open("live_data.csv", "a", newline='') as f:
            f.write(f"{step},{q_j1},{q_j7},{flow_ew},{flow_ns},{amb_active},{co2_j1},{co2_j7},{cars_j1},{cars_j7},{t_car},{t_amb},{t_bus},{t_ped},{t_truck}\n")
            
    step += 1

traci.close()
print("✅ Corridor Simulation Complete!")