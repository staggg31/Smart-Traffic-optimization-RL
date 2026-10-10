import traci

traci.start([
    "sumo",
    "-c", "environment/simulation.sumocfg"
])

print("Traffic light IDs:", traci.trafficlight.getIDList())

traci.close()
