import traci
import sys
import os

# 1. Setup SUMO Home (Standard Safety Check)
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("Please declare environment variable 'SUMO_HOME'")

# 2. Start SUMO GUI
# We use your config file 'mysim.sumocfg'
sumoCmd = ["sumo-gui", "-c", "mysim.sumocfg"]
traci.start(sumoCmd)

# 3. Main Loop
step = 0
tls_id = "J7"  # YOUR Traffic Light ID (Double check this in NetEdit if it crashes!)

print("Starting Simulation...")

while step < 1000:
    # Move simulation forward 1 second
    traci.simulationStep()
    
    # LOGIC: Switch Green Light every 40 steps
    # Phase 0 is usually North-South Green
    # Phase 2 is usually East-West Green
    
    if step % 80 == 0:
        print(f"Step {step}: Switching to North-South Green (Phase 0)")
        traci.trafficlight.setPhase(tls_id, 0)
        
    elif step % 80 == 40:
        print(f"Step {step}: Switching to East-West Green (Phase 2)")
        traci.trafficlight.setPhase(tls_id, 2)

    step += 1

print("Simulation finished.")
traci.close()