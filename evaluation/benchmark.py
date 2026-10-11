"""Reproducible baseline experiment benchmark comparing FixedTime and Actuated controllers.

This script executes matched experiments on the research intersection network across
designated random seeds, exports structured JSON and CSV reports to results/baselines/,
and prints an executive statistical summary.
"""

import csv
import json
import os
import sys
from typing import Any, Dict, List

# Ensure workspace root is in sys.path
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config.schema import IntersectionConfig

from controllers.actuated import ActuatedController
from controllers.fixed_time import FixedTimeController
from environment.reward import RewardCalculator, RewardScalingConfig, RewardWeights
from environment.sumo_environment import SumoEnvironment
from evaluation.runner import ExperimentResult, run_simulation_experiment


def build_experiment_config() -> IntersectionConfig:
    """Build canonical IntersectionConfig for the research intersection."""
    return IntersectionConfig(
        tls_id="C",
        incoming_lanes=[
            "N_in_0", "N_in_1",
            "S_in_0", "S_in_1",
            "E_in_0", "E_in_1",
            "W_in_0", "W_in_1",
        ],
        green_phase_indices=[0, 2],
        min_green_seconds=5.0,
        max_green_seconds=45.0,
        control_interval_seconds=1.0,
        yellow_seconds=3.0,
        all_red_seconds=0.0,
        clearance_handled_by_sumo=True,
        exit_lanes=[
            "N_out_0", "N_out_1",
            "S_out_0", "S_out_1",
            "E_out_0", "E_out_1",
            "W_out_0", "W_out_1",
        ],
    )


def build_default_reward_calculator() -> RewardCalculator:
    """Build calibrated RewardCalculator for evaluation."""
    scales = RewardScalingConfig(
        waiting_time_ref_seconds=100.0,
        queue_ref_vehicles=10.0,
        stops_ref_vehicles=5.0,
        emissions_ref_mg=100000.0,
        throughput_ref_vehicles=10.0,
    )
    weights = RewardWeights(
        w_waiting_time=1.0,
        w_queue=0.5,
        w_stops=0.1,
        w_emissions=0.1,
        w_throughput=0.5,
    )
    return RewardCalculator(scales, weights)


def run_benchmarks(
    seeds: List[int],
    output_dir: str = "results/baselines",
) -> List[Dict[str, Any]]:
    """Execute matched baseline experiments across seeds."""
    os.makedirs(output_dir, exist_ok=True)
    cfg = build_experiment_config()
    net = os.path.abspath("environment/single_intersection.net.xml")
    rou = os.path.abspath("environment/routes.rou.xml")

    records: List[Dict[str, Any]] = []

    for seed in seeds:
        print(f"--- Running Seed {seed} ---")
        # 1. Fixed-Time Controller
        reward_calc_ft = build_default_reward_calculator()
        env_ft = SumoEnvironment(cfg, net, rou, reward_calculator=reward_calc_ft)
        ctrl_ft = FixedTimeController.from_config(cfg, default_green_seconds=42.0)
        res_ft = run_simulation_experiment(env_ft, ctrl_ft, seed=seed, close_env=True)
        rec_ft = res_ft.summary()
        rec_ft["seed"] = seed
        records.append(rec_ft)

        # 2. Actuated Controller
        reward_calc_act = build_default_reward_calculator()
        env_act = SumoEnvironment(cfg, net, rou, reward_calculator=reward_calc_act)
        ctrl_act = ActuatedController.from_config(cfg, queue_threshold=0.5)
        res_act = run_simulation_experiment(env_act, ctrl_act, seed=seed, close_env=True)
        rec_act = res_act.summary()
        rec_act["seed"] = seed
        records.append(rec_act)

    # Save to JSON
    json_path = os.path.join(output_dir, "baseline_comparison_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    print(f"Saved benchmark results to {json_path}")

    # Save to CSV
    csv_path = os.path.join(output_dir, "baseline_comparison_results.csv")
    if records:
        keys = list(records[0].keys())
        # Filter out step_records from CSV header if empty
        keys = [k for k in keys if k != "step_records"]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            writer.writeheader()
            for r in records:
                writer.writerow(r)
        print(f"Saved benchmark CSV to {csv_path}")

    return records


if __name__ == "__main__":
    # Test on seeds 42, 101, 202
    test_seeds = [42, 101, 202]
    results = run_benchmarks(test_seeds)
