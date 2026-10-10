
import traci

sumo_cmd = [
    "sumo",
    "-c", "environment/simulation.sumocfg"
]

traci.start(sumo_cmd)

print("SUMO connected to Python!")

while traci.simulation.getMinExpectedNumber() > 0:
    traci.simulationStep()

    vehicles = traci.vehicle.getIDList()
    print("Time:", traci.simulation.getTime(),
          "| Vehicles:", len(vehicles))

traci.close()
print("Simulation completed!")
