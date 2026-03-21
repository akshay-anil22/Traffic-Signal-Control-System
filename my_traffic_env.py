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
        # 0 = Keep the current light phase
        # 1 = Switch to the next phase
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
        
        # Start SUMO
        traci.start(self.sumo_cmd)
        
        # Return the first "sight" of the world (0 cars initially)
        return np.zeros(9, dtype=np.float32), {}

    def step(self, action):
        """The AI takes an action, and we tell it what happened."""
        
        current_phase = traci.trafficlight.getPhase(self.tls_id)
        reward = 0

        # --- 1. APPLY ACTION & FAST FORWARD ---
        if action == 1:
            # Step A: Switch to the Yellow phase
            traci.trafficlight.setPhase(self.tls_id, (current_phase + 1) % 8)
            
            # Step B: Force the simulation to run for 3 seconds on Yellow. 
            for _ in range(3):
                traci.simulationStep()
                
            # Step C: Switch to the next actual Green phase
            traci.trafficlight.setPhase(self.tls_id, (current_phase + 2) % 8)
            
            # Step D: Force the New Green Phase to stay on for at least 10 seconds
            for _ in range(10):
                traci.simulationStep()
                
            # Big penalty for causing a switch
            reward -= 50

        else: # Action 0 (Keep)
            # If the AI decides to keep the light green, let it run for 5 seconds
            for _ in range(5):
                traci.simulationStep()


        # --- 2. GET NEW STATE (The "Eyes" Upgrade) ---
        observations = []
        for lane in self.lanes:
            # Count exactly how many cars are stopped at this exact moment
            stopped_cars = traci.lane.getLastStepHaltingNumber(lane)
            observations.append(stopped_cars)
        
        # Tell the AI what phase the light is currently on
        new_phase = traci.trafficlight.getPhase(self.tls_id)
        observations.append(new_phase)
        
        state = np.array(observations, dtype=np.float32)

        # --- 3. CALCULATE REWARD ---
        # Sum up the waiting time of all 8 lanes (ignoring the phase number at the end)
        total_wait_time = sum(observations[:-1])
        
        # Continuous punishment for making people wait
        reward -= total_wait_time 

        # --- 4. CHECK IF DONE ---
        terminated = traci.simulation.getTime() > 3600 # End after 1 hour of simulation time
        truncated = False
        
        return state, reward, terminated, truncated, {}