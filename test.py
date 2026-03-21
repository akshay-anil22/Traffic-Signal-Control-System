from stable_baselines3 import PPO
from my_traffic_env import TrafficEnv 
import traci
import time

# 1. Load the Environment
env = TrafficEnv()
env.sumo_cmd = ["sumo-gui", "-c", "mysim.sumocfg", "--start", "--no-step-log", "true"]

# 2. Load your trained Brain
print("🧠 Loading AI Brain...", flush=True)
model = PPO.load("traffic_ai_brain") 

# 3. Reset the world to start fresh
obs, _ = env.reset()
done = False

print("🚀 Starting simulation... Watch the SUMO window!", flush=True)

while not done:
    action, _ = model.predict(obs, deterministic=True)
    obs, reward, terminated, truncated, _ = env.step(action)
    done = terminated or truncated

    time.sleep(0.05) 

print("🛑 Simulation finished.", flush=True)

# Forcefully kill the SUMO connection so it doesn't leave ghost windows open!
try:
    traci.close()
except:
    pass