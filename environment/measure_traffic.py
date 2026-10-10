
import traci

traci.start([
    "sumo",
    "-c", "environment/simulation.sumocfg"
])

print("Traffic measurement started!")

while traci.simulation.getMinExpectedNumber() > 0:
    traci.simulationStep()

    time = int(traci.simulation.getTime())
    vehicles = traci.vehicle.getIDList()

    waiting = sum(
        1 for vehicle_id in vehicles
        if traci.vehicle.getWaitingTime(vehicle_id) > 0
    )

    print(
        f"Time: {time:2d}s | "
        f"Active vehicles: {len(vehicles)} | "
        f"Waiting vehicles: {waiting}"
    )

traci.close()
print("Traffic measurement completed!")
