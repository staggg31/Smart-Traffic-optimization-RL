import os
import traci

sumo = os.path.join(os.environ["SUMO_HOME"], "bin", "sumo.exe")
network = os.path.abspath("tests/smoke.net.xml")
routes = os.path.abspath("tests/smoke.rou.xml")

try:
    traci.start([
        sumo,
        "-n", network,
        "-r", routes,
        "--end", "100",
        "--no-step-log", "true"
    ])

    for _ in range(20):
        traci.simulationStep()

    print("SUCCESS: SUMO launched through TraCI!")
    print("Simulation time:", traci.simulation.getTime(), "seconds")
    print("Vehicles expected:", traci.simulation.getMinExpectedNumber())

finally:
    traci.close()
