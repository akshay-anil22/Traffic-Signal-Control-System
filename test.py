from stable_baselines3 import PPO
from my_traffic_env import TrafficEnv
import traci

# 1. Load the Environment
env = TrafficEnv()

# *** CRITICAL: Force GUI mode so we can see it ***
# We overwrite the command in the environment to make sure it opens the window.
env.sumo_cmd = ["sumo-gui", "-c", "mysim.sumocfg", "--start", "--quit-on-end", "--no-step-log", "true"]

# 2. Load your trained Brain
# We look for the "traffic_ai_brain.zip" file you just created.
model = PPO.load("traffic_ai_brain")

# 3. Reset the world to start fresh
obs, _ = env.reset()
done = False

print("Starting simulation... Watch the GUI window!")

while not done:
    # 4. Ask the AI: "What should I do?"
    # It looks at the observation (obs) and predicts the best action.
    action, _ = model.predict(obs)
    
    # 5. Do the action
    obs, reward, terminated, truncated, _ = env.step(action)
    done = terminated or truncated

    # Optional: Slow it down slightly so you can see what's happening
    # (Remove this if you want it to run at max speed)
    import time
    time.sleep(0.05) 

print("Simulation finished.")