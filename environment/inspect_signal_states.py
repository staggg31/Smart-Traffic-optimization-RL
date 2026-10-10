
import traci

traci.start([
    "sumo",
    "-c", "environment/simulation.sumocfg"
])

tls_id = "C"

programs = traci.trafficlight.getAllProgramLogics(tls_id)
logic = programs[0]

print("Traffic light:", tls_id)
print("Number of signal indices:",
      len(traci.trafficlight.getControlledLinks(tls_id)))

for phase_number, phase in enumerate(logic.phases):
    print(f"\nPhase {phase_number}")
    print("Duration:", phase.duration)
    print("State:", phase.state)

    for index, signal in enumerate(phase.state):
        print(f"  Signal {index}: {signal}")

traci.close()
