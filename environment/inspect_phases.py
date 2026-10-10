
import traci

traci.start([
    "sumo",
    "-c", "environment/simulation.sumocfg"
])

tls_id = "C"

programs = traci.trafficlight.getAllProgramLogics(tls_id)
phases = programs[0].phases

print("Traffic light ID:", tls_id)
print("Number of phases:", len(phases))

for i, phase in enumerate(phases):
    print(f"Phase {i}: duration={phase.duration}, state={phase.state}")

traci.close()
