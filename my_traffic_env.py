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
        # The AI will "see" the number of cars in 4 specific lanes.
        # We define a box of 4 numbers, ranging from 0 to 100 cars.
        self.observation_space = spaces.Box(low=0, high=10000, shape=(9,), dtype=np.float32)

        # 2. DEFINE THE "HANDS" (Action Space)
        # The AI has 2 buttons:
        # 0 = Keep the current light phase
        # 1 = Switch to the next phase
        self.action_space = spaces.Discrete(2)

        # 3. YOUR SPECIFIC CONFIGURATION
        self.sumo_cmd = ["sumo", "-c", "mysim.sumocfg", "--start", "--quit-on-end", "--no-step-log", "true", "--waiting-time-memory", "1000"]
        self.tls_id = "J7"  # <--- CONFIRM THIS ID IN NETEDIT!
        
        # *** CRITICAL: PUT YOUR INCOMING LANE IDs HERE ***
        # These are the lanes the AI watches to decide if it should switch.
        # Usually: [North_Incoming, East_Incoming, South_Incoming, West_Incoming]
        # Example: "E1_0" means Edge E1, Lane 0.
        self.lanes = ["E1_0", "-E0_0", "-E1_0", "E3_0","E1_1", "-E0_1", "-E1_1", "E3_1"] 

    def reset(self, seed=None, options=None):
        """Called at the start of every training episode."""
        try:
            traci.close()
        except:
            pass
        
        # Start SUMO
        traci.start(self.sumo_cmd)
        
        # Return the first "sight" of the world (0 cars initially)
        return np.zeros(9, dtype=np.float32), {}

    def step(self, action):
        """The AI takes an action, and we tell it what happened."""
        
        # --- 1. APPLY ACTION & PREVENT QUICK SWITCHING ---
        if action == 1:
            current_phase = traci.trafficlight.getPhase(self.tls_id)
            
            # Step A: Switch to the Yellow phase (which is always current_phase + 1)
            traci.trafficlight.setPhase(self.tls_id, (current_phase + 1) % 8)
            
            # Step B: Force the simulation to run for 4 seconds on Yellow. 
            # The AI CANNOT interrupt this. It prevents instant green-to-green switching.
            for _ in range(4):
                traci.simulationStep()
                
            # Step C: Now switch to the next actual Green phase
            traci.trafficlight.setPhase(self.tls_id, (current_phase + 2) % 8)
        
        # --- 2. FAST FORWARD THE GREEN LIGHT ---
        # The AI locks in its decision for 15 seconds. 
        # Increase this number to 20 or 30 if you want the lights to stay green even longer!
        for _ in range(15):
            traci.simulationStep()

        # --- 3. GET NEW STATE (The "Eyes" Upgrade) ---
        observations = []
        for lane in self.lanes:
            # UPGRADE: Measure total waiting time in seconds instead of just counting cars
            wait_time = traci.lane.getWaitingTime(lane)
            observations.append(wait_time)
        
        # UPGRADE: Tell the AI what phase the light is currently on
        current_phase = traci.trafficlight.getPhase(self.tls_id)
        observations.append(current_phase)
        
        state = np.array(observations, dtype=np.float32)

        # --- 4. CALCULATE REWARD (The "Grades" Upgrade) ---
        # We sum up the waiting time of all 8 lanes (we use [:-1] to ignore the phase number at the end)
        total_wait_time = sum(observations[:-1])
        
        # Big punishment for making people wait
        reward = -total_wait_time 

        # UPGRADE: Slap the AI with a penalty if it decides to switch the light
        if action == 1:
            reward -= 50  

        # --- 5. CHECK IF DONE ---
        terminated = traci.simulation.getTime() > 3600
        truncated = False
        
        return state, reward, terminated, truncated, {}