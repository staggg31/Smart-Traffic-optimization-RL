
import traci

traci.start([
    "sumo",
    "-c", "environment/simulation.sumocfg"
])

tls_id = "C"
links = traci.trafficlight.getControlledLinks(tls_id)

print("Traffic light:", tls_id)
print("Number of signal indices:", len(links))

for index, link_group in enumerate(links):
    print(f"\nSignal index {index}:")

    for incoming, outgoing, via in link_group:
        print("  Incoming lane:", incoming)
        print("  Outgoing lane:", outgoing)
        print("  Internal lane:", via)

traci.close()
