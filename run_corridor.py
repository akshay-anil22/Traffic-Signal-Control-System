import traci
import numpy as np
from stable_baselines3 import PPO
import csv
import os

# ==========================================
# 0. SETUP THE STREAMLIT BRIDGE
# ==========================================
# We added 'tot_triggers' to the very end of this header!
with open("live_data.csv", "w", newline='') as f:
    f.write("step,q_j1,q_j7,flow_ew,flow_ns,ambulance_active,co2_j1,co2_j7,cars_j1,cars_j7,tot_car,tot_amb,tot_bus,tot_ped,tot_truck,tot_triggers\n")

def handle_emergency(tls_id):
    lanes = list(set(traci.trafficlight.getControlledLanes(tls_id)))
    for lane in lanes:
        veh_ids = traci.lane.getLastStepVehicleIDs(lane)
        for veh_id in veh_ids:
            if traci.vehicle.getVehicleClass(veh_id) == "emergency":
                
                links = traci.trafficlight.getControlledLinks(tls_id)
                target_link_index = -1
                for i, link_group in enumerate(links):
                    if len(link_group) > 0 and link_group[0][0] == lane:
                        target_link_index = i
                        break
                        
                if target_link_index != -1:
                    # SMART CHECK: Is the light ALREADY green?
                    current_state = traci.trafficlight.getRedYellowGreenState(tls_id)
                    if current_state[target_link_index] in ['G', 'g']:
                        # It is already green! Do nothing. Let the AI take credit.
                        return False 
                        
                    # It is RED. We must force an override!
                    phases = traci.trafficlight.getCompleteRedYellowGreenDefinition(tls_id)[0].phases
                    for phase_idx, phase in enumerate(phases):
                        if phase.state[target_link_index] in ['G', 'g']:
                            traci.trafficlight.setPhase(tls_id, phase_idx)
                            print(f"🚨 TRUE OVERRIDE at {tls_id}! Forced a red light to green.")
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
sumo_cmd = ["sumo-gui", "-c", "mysim.sumocfg", "--start","--quit-on-end","--delay","160", "--gui-settings-file", "view.xml"]
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
total_true_triggers = 0 

# --- NEW: Cumulative Halted CO2 Trackers ---
total_co2_j1 = 0.0
total_co2_j7 = 0.0
halted_cars_j1 = set()
halted_cars_j7 = set()

step = 0
while step < 3600:
    traci.simulationStep()
    
    # ------------------------------------------
    # AI DECISION LOOP
    # ------------------------------------------
    for tls_id in tls_ids:
        is_emergency = handle_emergency(tls_id)
        if is_emergency:
            total_true_triggers += 1
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
        elif v_class in ["bus", "coach"]: seen_buses.add(v)
        elif v_class in ["truck", "trailer"]: seen_trucks.add(v)
        
        # --- NEW: HALTED CO2 TRACKER ---
        speed = traci.vehicle.getSpeed(v)
        if speed < 0.1: # If the car is stopped/idling
            edge = traci.vehicle.getRoadID(v)
            if edge in ["-E2", "-E4"]: # Incoming to J1
                total_co2_j1 += traci.vehicle.getCO2Emission(v)
                halted_cars_j1.add(v)
            elif edge in ["E1", "-E1"]: # Incoming to J7
                total_co2_j7 += traci.vehicle.getCO2Emission(v)
                halted_cars_j7.add(v)
        
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
        
        # 2. Output the Cumulative Halted Totals
        co2_j1 = total_co2_j1
        co2_j7 = total_co2_j7
        cars_j1 = len(halted_cars_j1)
        cars_j7 = len(halted_cars_j7)
        
        t_car = len(seen_cars)
        t_amb = len(seen_ambs)
        t_bus = len(seen_buses)
        t_ped = len(seen_peds)
        t_truck = len(seen_trucks)

        with open("live_data.csv", "a", newline='') as f:
            f.write(f"{step},{q_j1},{q_j7},{flow_ew},{flow_ns},{amb_active},{co2_j1},{co2_j7},{cars_j1},{cars_j7},{t_car},{t_amb},{t_bus},{t_ped},{t_truck},{total_true_triggers}\n")
            
    step += 1

traci.close()

# ==========================================
# 3. SAVE FINAL RESULTS TO HISTORY
# ==========================================
# Convert total mg from both junctions into kg
final_co2_kg = (total_co2_j1 + total_co2_j7) / 1000000.0

# Check if the history file exists. If not, create it with a header.
history_file = "episode_summary.csv"
file_exists = os.path.isfile(history_file)

with open(history_file, "a", newline='') as f:
    if not file_exists:
        f.write("co2_kg\n") # Create the header if it's a new file
    f.write(f"{final_co2_kg:.4f}\n") # Save this run's total CO2

print(f"✅ Corridor Simulation Complete! Saved {final_co2_kg:.2f} kg to history.")