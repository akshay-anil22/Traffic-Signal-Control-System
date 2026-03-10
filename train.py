from stable_baselines3 import PPO
from my_traffic_env import TrafficEnv
import os

# 1. Create the Environment (The Classroom)
env = TrafficEnv()

# 2. Create the Agent (The Student)
# MlpPolicy = "Multi-Layer Perceptron" (A basic brain)
# verbose=1 = "Tell me what's happening in the terminal"
model = PPO("MlpPolicy", env, verbose=1)

# 3. Start Training
print("Training started... (SUMO will open and close many times)")
# 20,000 steps is a quick "Test Run". For real genius AI, use 1,000,000.
model.learn(total_timesteps=1000000)

# 4. Save the Brain
model.save("traffic_ai_brain")
print("Training complete! Brain saved as 'traffic_ai_brain.zip'")