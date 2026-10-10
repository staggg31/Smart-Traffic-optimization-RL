
import traci

sumo_cmd = [
    "sumo",
    "-c", "environment/simulation.sumocfg"
]

traci.start(sumo_cmd)

tls_id = "C"

print("Connected to SUMO!")
print("Traffic light:", tls_id)

while traci.simulation.getMinExpectedNumber() > 0:
    traci.simulationStep()

    signal_state = traci.trafficlight.getRedYellowGreenState(tls_id)

    waiting_vehicles = 0

    for vehicle_id in traci.vehicle.getIDList():
        if traci.vehicle.getWaitingTime(vehicle_id) > 0:
            waiting_vehicles += 1

    print(
        "Time:", int(traci.simulation.getTime()),
        "| Signal:", signal_state,
        "| Waiting vehicles:", waiting_vehicles
    )

traci.close()
print("Controller test completed!")
