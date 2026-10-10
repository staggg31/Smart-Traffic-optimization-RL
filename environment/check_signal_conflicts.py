
import xml.etree.ElementTree as ET

NET_FILE = "environment/single_intersection.net.xml"

tree = ET.parse(NET_FILE)
root = tree.getroot()

junction = root.find(".//junction[@id='C']")

if junction is None:
    print("Junction C not found.")
    raise SystemExit

requests = {
    int(req.get("index")): req
    for req in junction.findall("request")
}

print("Junction:", junction.get("id"))
print("Checking conflict data for 20 signal indices...\n")

for i in range(20):
    req = requests.get(i)

    if req is None:
        print(f"Signal {i}: request data missing")
        continue

    print(
        f"Signal {i}: "
        f"foes={req.get('foes')} "
        f"response={req.get('response')}"
    )

print("\nRead-only check complete.")
print("This script does not change signal timings.")

