"""Reproducible traffic demand generator for the research intersection.

This module generates verified, reproducible SUMO route XML files based on Poisson
vehicle arrivals across the 4 valid incoming edges (N_in, S_in, E_in, W_in) with
destination edge assignment strictly respecting verified network turn connections.
All generated route files are stored in data/routes/ to preserve the original
regression fixture (environment/routes.rou.xml).
"""

import argparse
import math
import os
import sys
from typing import Any, Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET


# Supported incoming to outgoing valid route connections verified from single_intersection.net.xml:
# N_in: straight -> S_out (weight 0.6), right -> W_out (weight 0.2), left -> E_out (weight 0.2)
# S_in: straight -> N_out (weight 0.6), right -> E_out (weight 0.2), left -> W_out (weight 0.2)
# E_in: straight -> W_out (weight 0.6), right -> N_out (weight 0.2), left -> S_out (weight 0.2)
# W_in: straight -> E_out (weight 0.6), right -> S_out (weight 0.2), left -> N_out (weight 0.2)
VALID_ROUTES = {
    "N_in": [("S_out", 0.6), ("W_out", 0.2), ("E_out", 0.2)],
    "S_in": [("N_out", 0.6), ("E_out", 0.2), ("W_out", 0.2)],
    "E_in": [("W_out", 0.6), ("N_out", 0.2), ("S_out", 0.2)],
    "W_in": [("E_out", 0.6), ("S_out", 0.2), ("N_out", 0.2)],
}

# Standard experimental target flow levels (total intersection veh/hr)
# 4 approaches share the total flow evenly (e.g. 400 total -> 100 veh/hr/approach)
DEMAND_LEVELS = {
    "low": 400.0,       # 100 veh/hr per approach
    "medium": 1200.0,   # 300 veh/hr per approach
    "high": 2400.0,     # 600 veh/hr per approach (heavy demand)
}


def generate_traffic_demand(
    output_file: str,
    total_flow_veh_per_hr: float,
    duration_seconds: float = 3600.0,
    warmup_seconds: float = 0.0,
    seed: int = 42,
    approach_weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Generate a valid SUMO routes XML file with reproducible vehicle departures.

    Args:
        output_file: Destination path for the generated .rou.xml file.
        total_flow_veh_per_hr: Total intersection arrival rate in vehicles/hour.
        duration_seconds: Total time window (seconds) during which vehicles depart.
        warmup_seconds: Start time (seconds) for vehicle departures.
        seed: Random seed for reproducible generation.
        approach_weights: Optional weights for distributing flow across the 4 approaches.
            Defaults to equal 0.25 for N_in, S_in, E_in, W_in.

    Returns:
        Dict[str, Any]: Generation statistics (vehicle count, flow rates, output path).

    Raises:
        ValueError: If flow rate or duration is non-positive.
    """
    if (
        isinstance(total_flow_veh_per_hr, bool)
        or not isinstance(total_flow_veh_per_hr, (int, float))
        or not math.isfinite(total_flow_veh_per_hr)
        or total_flow_veh_per_hr <= 0
    ):
        raise ValueError(f"total_flow_veh_per_hr must be a positive finite number, got {total_flow_veh_per_hr!r}.")

    if (
        isinstance(duration_seconds, bool)
        or not isinstance(duration_seconds, (int, float))
        or not math.isfinite(duration_seconds)
        or duration_seconds <= 0
    ):
        raise ValueError(f"duration_seconds must be a positive finite number, got {duration_seconds!r}.")

    import numpy as np
    rng = np.random.RandomState(seed)

    if approach_weights is None:
        approach_weights = {"N_in": 0.25, "S_in": 0.25, "E_in": 0.25, "W_in": 0.25}

    # Ensure output directory exists
    out_dir = os.path.dirname(output_file)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    vehicles: List[Tuple[float, str, str, str]] = []  # (depart_time, veh_id, from_edge, to_edge)
    veh_counter = 0

    for approach, weight in approach_weights.items():
        if approach not in VALID_ROUTES:
            raise ValueError(f"Approach edge {approach} not in valid routes.")

        approach_flow_per_sec = (total_flow_veh_per_hr * weight) / 3600.0
        # Expected inter-arrival time (Poisson process -> exponential inter-arrivals)
        mean_headway = 1.0 / approach_flow_per_sec

        current_time = warmup_seconds + rng.exponential(mean_headway)
        destinations = [d[0] for d in VALID_ROUTES[approach]]
        dest_probs = [d[1] for d in VALID_ROUTES[approach]]

        while current_time < duration_seconds:
            chosen_dest = rng.choice(destinations, p=dest_probs)
            vid = f"{approach}_{chosen_dest}_{veh_counter}"
            veh_counter += 1
            vehicles.append((current_time, vid, approach, chosen_dest))
            current_time += rng.exponential(mean_headway)

    # Sort vehicles chronologically by departure time
    vehicles.sort(key=lambda v: v[0])

    # Build XML document
    root = ET.Element("routes")
    # Vehicle type matching standard passenger car
    ET.SubElement(
        root,
        "vType",
        id="car",
        vClass="passenger",
        accel="2.6",
        decel="4.5",
        sigma="0.5",
        length="5.0",
        maxSpeed="13.89",
    )

    # Define canonical route IDs
    route_map: Dict[Tuple[str, str], str] = {}
    for from_edge, to_edge_list in VALID_ROUTES.items():
        for to_edge, _ in to_edge_list:
            rid = f"route_{from_edge}_{to_edge}"
            route_map[(from_edge, to_edge)] = rid
            ET.SubElement(root, "route", id=rid, edges=f"{from_edge} {to_edge}")

    for depart, vid, from_edge, to_edge in vehicles:
        rid = route_map[(from_edge, to_edge)]
        ET.SubElement(
            root,
            "vehicle",
            id=vid,
            type="car",
            route=rid,
            depart=f"{depart:.2f}",
        )

    # Format XML with indentation
    ET.indent(root, space="    ")
    tree = ET.ElementTree(root)
    tree.write(output_file, encoding="utf-8", xml_declaration=True)

    stats = {
        "output_file": os.path.abspath(output_file),
        "total_vehicles": len(vehicles),
        "target_flow_veh_per_hr": float(total_flow_veh_per_hr),
        "actual_flow_veh_per_hr": float(len(vehicles) / (duration_seconds / 3600.0)),
        "duration_seconds": float(duration_seconds),
        "seed": int(seed),
    }
    return stats


def generate_benchmark_scenarios(
    output_dir: str = "data/routes",
    duration_seconds: float = 600.0,
    seed: int = 42,
) -> Dict[str, Dict[str, Any]]:
    """Generate the standard low, medium, and high demand route files."""
    os.makedirs(output_dir, exist_ok=True)
    results = {}
    for level, flow in DEMAND_LEVELS.items():
        fname = os.path.join(output_dir, f"demand_{level}_seed{seed}.rou.xml")
        stats = generate_traffic_demand(
            output_file=fname,
            total_flow_veh_per_hr=flow,
            duration_seconds=duration_seconds,
            seed=seed,
        )
        results[level] = stats
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate reproducible traffic demand for SUMO.")
    parser.add_argument("--level", "--flow", dest="level", choices=["low", "medium", "high", "all"], default="all", help="Demand level (low, medium, high, all)")
    parser.add_argument("--duration", type=float, default=600.0, help="Duration in seconds (default 600s)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default 42)")
    parser.add_argument("--outdir", default="data/routes", help="Output directory")
    parser.add_argument("--output", default=None, help="Explicit destination file path (overrides outdir and standard name)")

    args = parser.parse_args()

    if args.output:
        lvl = "medium" if args.level == "all" else args.level
        flow = DEMAND_LEVELS[lvl]
        s = generate_traffic_demand(args.output, total_flow_veh_per_hr=flow, duration_seconds=args.duration, seed=args.seed)
        print(f"Generated {lvl} demand: {s['total_vehicles']} vehicles -> {s['output_file']}")
    elif args.level == "all":
        res = generate_benchmark_scenarios(output_dir=args.outdir, duration_seconds=args.duration, seed=args.seed)
        for lvl, s in res.items():
            print(f"Generated {lvl} demand: {s['total_vehicles']} vehicles -> {s['output_file']}")
    else:
        flow = DEMAND_LEVELS[args.level]
        out_f = os.path.join(args.outdir, f"demand_{args.level}_seed{args.seed}.rou.xml")
        s = generate_traffic_demand(out_f, total_flow_veh_per_hr=flow, duration_seconds=args.duration, seed=args.seed)
        print(f"Generated {args.level} demand: {s['total_vehicles']} vehicles -> {s['output_file']}")
