"""Tri-controller evaluation benchmark comparing FixedTime, Actuated, and PPO controllers.

This module evaluates all three controllers under identical conditions on matched
demand levels (Low, Medium, High, or Regression) across held-out evaluation seeds.
It exports raw per-run CSV records, detailed JSON summaries, and aggregate statistical tables
(mean ± sample std) to results/evaluations/.
"""

import argparse
import csv
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

# Ensure workspace root is in sys.path
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import numpy as np

from config.schema import IntersectionConfig
from controllers.actuated import ActuatedController
from controllers.fixed_time import FixedTimeController
from controllers.ppo import PPOController
from environment.observation import ObservationBuilder, ObservationNormalizerConfig
from environment.reward import RewardCalculator, RewardScalingConfig, RewardWeights
from environment.sumo_environment import SumoEnvironment
from evaluation.runner import ExperimentResult, run_simulation_experiment


def build_evaluation_config() -> IntersectionConfig:
    """Build canonical IntersectionConfig for research intersection TLS C."""
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


def make_eval_environment(
    route_file: str,
    net_file: Optional[str] = None,
    max_steps: int = 500,
) -> SumoEnvironment:
    """Instantiate a standardized SumoEnvironment with normalized observations."""
    config = build_evaluation_config()
    net = os.path.abspath(net_file or "environment/single_intersection.net.xml")
    routes = os.path.abspath(route_file)

    norm_cfg = ObservationNormalizerConfig(
        max_queue_per_lane=20.0,
        max_vehicles_per_lane=25.0,
        max_waiting_time_seconds=100.0,
        speed_limit_mps=13.89,
        max_green_seconds=45.0,
    )
    obs_builder = ObservationBuilder(
        lane_order=config.incoming_lanes,
        green_phase_order=config.green_phase_indices,
        normalizer_config=norm_cfg,
    )

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
    reward_calc = RewardCalculator(scales, weights)

    return SumoEnvironment(
        config=config,
        net_file=net,
        route_file=routes,
        observation_builder=obs_builder,
        reward_calculator=reward_calc,
        max_steps=max_steps,
    )


def evaluate_tri_controllers(
    route_file: str,
    ppo_model_path: Optional[str] = None,
    seeds: List[int] = [301, 302, 303],
    output_dir: str = "results/evaluations",
    max_steps: int = 500,
    actuated_queue_threshold: float = 0.5,
) -> Dict[str, Any]:
    """Execute evaluation comparing FixedTime, Actuated, and PPO on identical seeds and demand.

    Args:
        route_file: Path to SUMO route demand file.
        ppo_model_path: Optional path to trained PPO model. If None, evaluates FT and Actuated.
        seeds: List of evaluation random seeds (strictly separate from training seeds).
        output_dir: Directory to save evaluation outputs.
        max_steps: Maximum decision steps per episode.
        actuated_queue_threshold: Queue threshold for ActuatedController (default 0.5).

    Returns:
        Dict[str, Any]: Evaluation summary including per-run and aggregate statistics.
    """
    os.makedirs(output_dir, exist_ok=True)
    cfg = build_evaluation_config()
    raw_results: List[Dict[str, Any]] = []

    controllers_to_test = [
        ("FixedTimeController", lambda: FixedTimeController.from_config(cfg, default_green_seconds=42.0)),
        ("ActuatedController", lambda: ActuatedController.from_config(cfg, queue_threshold=actuated_queue_threshold)),
    ]
    if ppo_model_path and os.path.exists(ppo_model_path):
        controllers_to_test.append(
            ("PPOController", lambda: PPOController(ppo_model_path, deterministic=True))
        )

    for ctrl_name, ctrl_factory in controllers_to_test:
        for seed in seeds:
            print(f"Evaluating {ctrl_name} on seed {seed}...")
            env = make_eval_environment(route_file=route_file, max_steps=max_steps)
            ctrl = ctrl_factory()
            res = run_simulation_experiment(env, ctrl, seed=seed, close_env=True)

            summary = res.summary()
            summary["seed"] = seed
            summary["route_file"] = os.path.basename(route_file)
            raw_results.append(summary)

    # 1. Save raw per-run results to JSON
    json_path = os.path.join(output_dir, "evaluation_raw_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(raw_results, f, indent=2)

    # 2. Save raw per-run results to CSV
    csv_path = os.path.join(output_dir, "evaluation_raw_results.csv")
    if raw_results:
        fields = [k for k in raw_results[0].keys() if k != "step_records"]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for r in raw_results:
                writer.writerow(r)

    # 3. Compute aggregate statistics (mean ± sample std)
    aggregates: Dict[str, Dict[str, Any]] = {}
    metric_keys = [
        "total_throughput_vehicles",
        "simulation_time_seconds",
        "total_steps",
        "mean_waiting_time_seconds",
        "mean_queue_vehicles",
        "total_stops",
        "total_emissions_mg",
        "total_reward",
        "phase_switches",
    ]

    for ctrl_name, _ in controllers_to_test:
        ctrl_runs = [r for r in raw_results if r["controller_name"] == ctrl_name]
        aggregates[ctrl_name] = {}
        for m in metric_keys:
            vals = [float(r[m]) for r in ctrl_runs if r.get(m) is not None]
            if len(vals) > 0:
                mean_val = float(np.mean(vals))
                std_val = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
                aggregates[ctrl_name][m] = {
                    "mean": mean_val,
                    "sample_std": std_val,
                }

    agg_json_path = os.path.join(output_dir, "evaluation_summary.json")
    with open(agg_json_path, "w", encoding="utf-8") as f:
        json.dump(aggregates, f, indent=2)

    # Save summary table CSV
    agg_csv_path = os.path.join(output_dir, "evaluation_summary.csv")
    summary_rows = []
    for ctrl_name, metrics in aggregates.items():
        row = {"controller_name": ctrl_name}
        for m, s in metrics.items():
            row[f"{m}_mean"] = s["mean"]
            row[f"{m}_std"] = s["sample_std"]
        summary_rows.append(row)

    if summary_rows:
        with open(agg_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
            writer.writeheader()
            for r in summary_rows:
                writer.writerow(r)

    print(f"Saved evaluation raw records to {json_path} and summary to {agg_json_path}")
    return {
        "raw_results": raw_results,
        "aggregates": aggregates,
        "raw_json_path": json_path,
        "raw_csv_path": csv_path,
        "summary_json_path": agg_json_path,
        "summary_csv_path": agg_csv_path,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate FixedTime, Actuated, and PPO controllers.")
    parser.add_argument("--routes", default="environment/routes.rou.xml", help="Path to route file")
    parser.add_argument("--model", default="models/ppo_smoke/ppo_traffic_final.zip", help="Path to trained PPO model")
    parser.add_argument("--seeds", nargs="+", type=int, default=[301, 302, 303], help="Evaluation seeds")
    parser.add_argument("--outdir", default="results/evaluations", help="Output directory")
    parser.add_argument("--max_steps", type=int, default=300, help="Max episode steps")
    parser.add_argument("--actuated_threshold", type=float, default=0.5, help="Actuated controller queue threshold (default 0.5)")

    args = parser.parse_args()

    evaluate_tri_controllers(
        route_file=args.routes,
        ppo_model_path=args.model if os.path.exists(args.model) else None,
        seeds=args.seeds,
        output_dir=args.outdir,
        max_steps=args.max_steps,
        actuated_queue_threshold=args.actuated_threshold,
    )
