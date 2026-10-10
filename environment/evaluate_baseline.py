
import traci

sumo_cmd = [
    "sumo",
    "-c", "environment/simulation.sumocfg"
]

traci.start(sumo_cmd)

# Store information for each vehicle
vehicle_start_times = {}
vehicle_waiting_times = {}
completed_travel_times = []
completed_waiting_times = []

print("Evaluating fixed-time traffic signal...")

while traci.simulation.getMinExpectedNumber() > 0:
    traci.simulationStep()
    current_time = traci.simulation.getTime()

    # Record newly observed vehicles
    for vehicle_id in traci.vehicle.getIDList():
        if vehicle_id not in vehicle_start_times:
            vehicle_start_times[vehicle_id] = current_time
            vehicle_waiting_times[vehicle_id] = 0.0

        # SUMO's cumulative waiting time in seconds
        vehicle_waiting_times[vehicle_id] = (
            traci.vehicle.getAccumulatedWaitingTime(vehicle_id)
        )

    # Record vehicles that finished this step
    for vehicle_id in traci.simulation.getArrivedIDList():
        if vehicle_id in vehicle_start_times:
            completed_travel_times.append(
                current_time - vehicle_start_times[vehicle_id]
            )
            completed_waiting_times.append(
                vehicle_waiting_times.get(vehicle_id, 0.0)
            )

traci.close()

print("\n--- Fixed-Time Baseline Results ---")
print("Vehicles completed:", len(completed_travel_times))

if completed_travel_times:
    avg_travel = sum(completed_travel_times) / len(
        completed_travel_times
    )
    avg_wait = sum(completed_waiting_times) / len(
        completed_waiting_times
    )
    total_wait = sum(completed_waiting_times)

    print(f"Average travel time: {avg_travel:.2f} seconds")
    print(f"Average waiting time: {avg_wait:.2f} seconds")
    print(f"Total waiting time: {total_wait:.2f} seconds")
else:
    print("No completed trips recorded.")
