import gymnasium as gym
from gymnasium import spaces
import traci
import numpy as np
import os
import sys

class TrafficEnv(gym.Env):
    def __init__(self):
        super(TrafficEnv, self).__init__()

        # 1. DEFINE THE "EYES" (Observation Space)
        self.observation_space = spaces.Box(low=0, high=10000, shape=(9,), dtype=np.float32)

        # 2. DEFINE THE "HANDS" (Action Space)
        self.action_space = spaces.Discrete(2)

        # 3. YOUR SPECIFIC CONFIGURATION
        self.sumo_cmd = ["sumo", "-c", "train_sim.sumocfg", "--start", "--quit-on-end", "--no-step-log", "true", "--waiting-time-memory", "1000"]
        self.tls_id = "J7"  
        
        # *** CRITICAL: PUT YOUR INCOMING LANE IDs HERE ***
        self.lanes = ["E1_0", "-E0_0", "-E1_0", "E3_0","E1_1", "-E0_1", "-E1_1", "E3_1"] 

        # Tracker for total CO2 emissions (in milligrams)
        self.total_co2 = 0.0

    def reset(self, seed=None, options=None):
        """Called at the start of every training episode."""
        try:
            traci.close()
        except:
            pass

        self.total_co2 = 0.0
        
        traci.start(self.sumo_cmd)
        return np.zeros(9, dtype=np.float32), {}

    def check_and_handle_emergency(self, tls_id, lane_to_phase_map):
        """Globally searches for an ambulance and manages the intersection phases."""
        
        all_vehicles = traci.vehicle.getIDList()
        
        for veh_id in all_vehicles:
            if traci.vehicle.getVehicleClass(veh_id) == "emergency":
                current_lane = traci.vehicle.getLaneID(veh_id)
                
                # 1. THE APPROACH (Incoming Lanes)
                if current_lane in lane_to_phase_map:
                    green_phase_index = lane_to_phase_map[current_lane]
                    traci.trafficlight.setPhase(tls_id, green_phase_index)
                    return True # Keep the override active!
                    
                # 2. THE CROSSING (Internal Junction Lanes start with ':')
                elif current_lane.startswith(":"):
                    # The ambulance is physically inside the intersection. 
                    # We don't need to change the phase, but we MUST keep the override active!
                    return True 
                
                # 3. THE EXIT (Outgoing Lanes)
                else:
                    # The ambulance has cleared the intersection and is driving away.
                    # We ignore it so the AI can take control back.
                    pass 
                    
        return False # No ambulances are approaching or crossing


    def run_steps_with_emergency_monitor(self, steps, lane_to_phase_map):
        """Fast-forwards the simulation and tracks CO2 emissions and checks for ambulances EVERY SINGLE SECOND."""
        was_emergency = False

        for _ in range(steps):    
            # Note: We removed 'self.lanes' from the parameters here since it searches globally now
            is_emergency = self.check_and_handle_emergency(self.tls_id, lane_to_phase_map)
            
            if is_emergency:
                was_emergency = True
                # Keep stepping until the ambulance has left our incoming lanes
                while self.check_and_handle_emergency(self.tls_id, lane_to_phase_map):
                    traci.simulationStep()
                    # Track CO2 even while the ambulance is crossing
                    for lane in self.lanes:
                        self.total_co2 += traci.lane.getCO2Emission(lane)
                
                print("✅ Ambulance cleared the intersection. Returning control to AI.", flush=True)
                return True # We were interrupted

            traci.simulationStep()

            # --- CO2 CALCULATION ---
            # SUMO outputs CO2 in milligrams (mg) per second.
            for lane in self.lanes:
                self.total_co2 += traci.lane.getCO2Emission(lane)
            
        return was_emergency

    def step(self, action):
        """The AI takes an action, and we tell it what happened."""
        
        # --- FIXED PHASE MAP (Only uses 0 to 5) ---
        # North/South lanes trigger Phase 0. East/West lanes trigger Phase 3.
        lane_to_phase_map = {
            "E1_0": 0, "E1_1": 0, "-E1_0": 0, "-E1_1": 0, 
            "-E0_0": 3, "-E0_1": 3, "E3_0": 3, "E3_1": 3
        }

        current_phase = traci.trafficlight.getPhase(self.tls_id)
        reward = 0
        was_emergency = False

        # --- 1. NORMAL AI LOGIC (Guarded by the emergency monitor) ---
        if action == 1:
            # Step A: Pedestrian Clearance (5 seconds)
            traci.trafficlight.setPhase(self.tls_id, (current_phase + 1) % 6)
            self.run_steps_with_emergency_monitor(5, lane_to_phase_map)
            
            # Step B: Yellow light (3 seconds)
            current_phase = traci.trafficlight.getPhase(self.tls_id)
            traci.trafficlight.setPhase(self.tls_id, (current_phase + 1) % 6)
            self.run_steps_with_emergency_monitor(3, lane_to_phase_map)
            
            # Step C: New Green light (10 seconds)
            current_phase = traci.trafficlight.getPhase(self.tls_id)
            traci.trafficlight.setPhase(self.tls_id, (current_phase + 1) % 6)
            was_emergency = self.run_steps_with_emergency_monitor(10, lane_to_phase_map)
            
        else:
            # Action 0 (Keep): Just run for 5 seconds and check again
            was_emergency = self.run_steps_with_emergency_monitor(5, lane_to_phase_map)

        # --- 2. GET NEW STATE (Fixed Snowball Effect) ---
        observations = []
        for lane in self.lanes:
            # Snap-shot of stopped cars, not accumulated waiting time!
            stopped_cars = traci.lane.getLastStepHaltingNumber(lane)
            observations.append(stopped_cars)
        
        current_phase = traci.trafficlight.getPhase(self.tls_id)
        observations.append(current_phase)
        state = np.array(observations, dtype=np.float32)

        # --- 3. CALCULATE REWARD ---
        total_stopped_cars = sum(observations[:-1])
        reward -= total_stopped_cars 

        # --- EMERGENCY VEHICLE DETECTION ---
        for lane in self.lanes:
            vehicles = traci.lane.getLastStepVehicleIDs(lane)
            for veh_id in vehicles:
                if traci.vehicle.getTypeID(veh_id) == "emergency":
                    reward -= 1000

        # --- PEDESTRIAN DETECTION ---
        # Check the edges connecting to the junction for waiting pedestrians
        pedestrian_edges = ["E1", "-E0", "E3", "-E1"] 
        for edge in pedestrian_edges:
            waiting_peds = traci.edge.getLastStepPersonIDs(edge)
            for ped in waiting_peds:
                if traci.person.getSpeed(ped) < 0.1: # Only penalize if they are actually stopped/waiting
                    reward -= 5 

        # Only penalize the AI for switching if it was actually its choice 
        if action == 1 and not was_emergency:
            reward -= 50  

        # --- 4. CHECK IF DONE ---
        terminated = traci.simulation.getTime() > 3600
        truncated = False
        
        # If the 1-hour episode is finished, print and SAVE the final CO2 tally!
        if terminated:
            co2_in_kg = self.total_co2 / 1000000.0
            print(f"🌍 1-Hour Simulation Complete! Total CO2 Emitted: {co2_in_kg:.2f} kg", flush=True)
            
            # --- NEW: Append the final score to our history file ---
            file_exists = os.path.isfile("episode_summary.csv")
            with open("episode_summary.csv", "a") as f:
                if not file_exists:
                    f.write("co2_kg\n") # Write the header if it's the first time
                f.write(f"{co2_in_kg}\n") # Save the value
        
        return state, reward, terminated, truncated, {}