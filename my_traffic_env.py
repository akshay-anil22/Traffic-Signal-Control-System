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
        self.sumo_cmd = ["sumo", "-c", "mysim.sumocfg", "--start", "--quit-on-end", "--no-step-log", "true", "--waiting-time-memory", "1000"]
        self.tls_id = "J7"  
        
        # *** CRITICAL: PUT YOUR INCOMING LANE IDs HERE ***
        self.lanes = ["E1_0", "-E0_0", "-E1_0", "E3_0","E1_1", "-E0_1", "-E1_1", "E3_1"] 

    def reset(self, seed=None, options=None):
        """Called at the start of every training episode."""
        try:
            traci.close()
        except:
            pass
        
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
        """Fast-forwards the simulation but checks for ambulances EVERY SINGLE SECOND."""
        for _ in range(steps):
            
            # Note: We removed 'self.lanes' from the parameters here since it searches globally now
            is_emergency = self.check_and_handle_emergency(self.tls_id, lane_to_phase_map)
            
            if is_emergency:
                # Keep stepping until the ambulance has left our incoming lanes
                while self.check_and_handle_emergency(self.tls_id, lane_to_phase_map):
                    traci.simulationStep()
                
                print("✅ Ambulance cleared the intersection. Returning control to AI.", flush=True)
                return True # We were interrupted

            traci.simulationStep()
            
        return False

    def step(self, action):
        """The AI takes an action, and we tell it what happened."""
        
        # *** YOUR SPECIFIC MAP GOES HERE ***
        lane_to_phase_map = {
            "E1_0": 0, "-E0_0": 4, "-E1_0": 0, "E3_0": 4,
            "E1_1": 2, "-E0_1": 6, "-E1_1": 2, "E3_1": 6
        }

        # --- 1. NORMAL AI LOGIC (Guarded by the emergency monitor) ---
        if action == 1:
            current_phase = traci.trafficlight.getPhase(self.tls_id)
            traci.trafficlight.setPhase(self.tls_id, (current_phase + 1) % 8)
            
            # Yellow light (4 seconds) - Watched by the monitor
            interrupted = self.run_steps_with_emergency_monitor(4, lane_to_phase_map)
            
            if not interrupted:
                # Only change to the AI's chosen green phase if an ambulance DIDN'T interrupt
                traci.trafficlight.setPhase(self.tls_id, (current_phase + 2) % 8)
        
        # Green light (15 seconds) - Watched by the monitor
        was_emergency = self.run_steps_with_emergency_monitor(15, lane_to_phase_map)

        # --- 2. GET NEW STATE ---
        observations = []
        for lane in self.lanes:
            wait_time = traci.lane.getWaitingTime(lane)
            observations.append(wait_time)
        
        current_phase = traci.trafficlight.getPhase(self.tls_id)
        observations.append(current_phase)
        state = np.array(observations, dtype=np.float32)

        # --- 3. CALCULATE REWARD ---
        total_wait_time = sum(observations[:-1])
        reward = -total_wait_time 

        # Only penalize the AI for switching if it was actually its choice (not forced by ambulance)
        if action == 1 and not was_emergency:
            reward -= 50  

        # --- 4. CHECK IF DONE ---
        terminated = traci.simulation.getTime() > 3600
        truncated = False
        
        return state, reward, terminated, truncated, {}