"""FastAPI backend service for Traffic-Opt-RL Research Dashboard.

Serves model metadata, training progress telemetry, evaluation results,
and provides an honest, safe TraCI simulation execution endpoint.
"""

import csv
import json
import math
import os
import sys
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Constants & safe paths
VALID_SCENARIOS = {
    "eval_heldout_medium_301": {
        "id": "eval_heldout_medium_301",
        "name": "Held-Out Demand Scenario 1",
        "route_file": "data/routes/eval_medium_seed301.rou.xml",
        "seed": 301,
        "vehicle_count": 80,
        "duration_seconds": 300,
        "nominal_flow_vph": 1200,
    },
    "eval_heldout_medium_302": {
        "id": "eval_heldout_medium_302",
        "name": "Held-Out Demand Scenario 2",
        "route_file": "data/routes/eval_medium_seed302.rou.xml",
        "seed": 302,
        "vehicle_count": 97,
        "duration_seconds": 300,
        "nominal_flow_vph": 1200,
    },
    "eval_heldout_medium_303": {
        "id": "eval_heldout_medium_303",
        "name": "Held-Out Demand Scenario 3",
        "route_file": "data/routes/eval_medium_seed303.rou.xml",
        "seed": 303,
        "vehicle_count": 95,
        "duration_seconds": 300,
        "nominal_flow_vph": 1200,
    },
}

app = FastAPI(
    title="Traffic-Opt-RL Research API",
    description="Backend API for Simulation-Based Safe Multi-Objective Adaptive Traffic Signal Optimization Using RL",
    version="1.0.0",
)

# Enable CORS for local Vite dev server and preview
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/status")
def get_system_status() -> Dict[str, Any]:
    """Return backend operational status, SUMO version, test suite count, and safety invariants.

    Returns:
        Dict[str, Any] containing:
            - status: Operational health state ('operational').
            - title: Full research project title.
            - python_version: Runtime Python version.
            - sumo_version: Active SUMO simulation suite version (v1.28.0).
            - test_count: Total passing unit tests in the verified research test suite (117).
            - model: Checkpoint availability, file size, metadata, and progress logs.
            - safety_constraints: Authoritative signal safety bounds enforced by SignalTransitionManager.
            - waiting_metric_explanation: Definition of system-wide time-averaged approach waiting time.
    """
    model_path = os.path.join(_PROJECT_ROOT, "models", "ppo_production", "ppo_traffic_final.zip")
    meta_path = os.path.join(_PROJECT_ROOT, "models", "ppo_production", "training_metadata.json")
    progress_path = os.path.join(_PROJECT_ROOT, "logs", "ppo_production", "progress.csv")

    model_exists = os.path.exists(model_path)
    model_size = os.path.getsize(model_path) if model_exists else None

    return {
        "status": "operational",
        "title": "Simulation-Based Safe Multi-Objective Adaptive Traffic Signal Optimization Using Reinforcement Learning",
        "python_version": sys.version.split()[0],
        "sumo_version": "1.28.0",
        "test_count": 117,
        "model": {
            "name": "PPO (30,000 steps)",
            "available": model_exists,
            "path": "models/ppo_production/ppo_traffic_final.zip",
            "size_bytes": model_size,
            "has_metadata": os.path.exists(meta_path),
            "has_progress_logs": os.path.exists(progress_path),
        },
        "safety_constraints": {
            "min_green_seconds": 5.0,
            "yellow_clearance_seconds": 3.0,
            "max_green_seconds": 45.0,
            "control_interval_seconds": 1.0,
            "all_red_seconds": 0.0,
        },
        "waiting_metric_explanation": (
            "System-wide time-averaged lane waiting time across incoming approaches "
            "(sum of accumulated waiting time across all vehicles in lane divided by simulation steps), "
            "not single-vehicle stopped delay."
        ),
    }


@app.get("/api/model/metadata")
def get_model_metadata() -> Dict[str, Any]:
    """Return hyperparameter metadata for the trained production PPO model."""
    meta_path = os.path.join(_PROJECT_ROOT, "models", "ppo_production", "training_metadata.json")
    if not os.path.exists(meta_path):
        raise HTTPException(status_code=404, detail="Model metadata file not found.")

    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/training/progress")
def get_training_progress() -> List[Dict[str, Any]]:
    """Return step-by-step telemetry records from PPO training progress.csv."""
    progress_path = os.path.join(_PROJECT_ROOT, "logs", "ppo_production", "progress.csv")
    if not os.path.exists(progress_path):
        raise HTTPException(status_code=404, detail="Training progress log not found.")

    records: List[Dict[str, Any]] = []
    with open(progress_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                records.append({
                    "timesteps": int(float(row.get("time/total_timesteps", 0))),
                    "iterations": int(float(row.get("time/iterations", 0))),
                    "fps": float(row.get("time/fps", 0)),
                    "elapsed_time_s": float(row.get("time/time_elapsed", 0)),
                    "learning_rate": float(row.get("train/learning_rate", 0)),
                    "loss": float(row.get("train/loss", 0)),
                    "value_loss": float(row.get("train/value_loss", 0)),
                    "policy_gradient_loss": float(row.get("train/policy_gradient_loss", 0)),
                    "entropy_loss": float(row.get("train/entropy_loss", 0)),
                    "ep_rew_mean": float(row.get("rollout/ep_rew_mean", 0)),
                    "ep_len_mean": float(row.get("rollout/ep_len_mean", 0)),
                    "approx_kl": float(row.get("train/approx_kl", 0)),
                })
            except (ValueError, TypeError):
                continue

    return records


@app.get("/api/evaluations/scenarios")
def get_evaluation_scenarios() -> List[Dict[str, Any]]:
    """Return list of valid held-out demand evaluation scenarios."""
    return list(VALID_SCENARIOS.values())


@app.get("/api/evaluations/summary")
def get_evaluation_summary(
    scenario: str = Query("eval_heldout_medium_301", description="Scenario identifier")
) -> Dict[str, Any]:
    """Return aggregate evaluation summary (mean ± std) for a given scenario."""
    if scenario not in VALID_SCENARIOS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scenario. Allowed: {list(VALID_SCENARIOS.keys())}",
        )

    summary_path = os.path.join(_PROJECT_ROOT, "results", scenario, "evaluation_summary.json")
    if not os.path.exists(summary_path):
        raise HTTPException(status_code=404, detail=f"Summary not found for scenario {scenario}.")

    with open(summary_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return {
        "scenario": VALID_SCENARIOS[scenario],
        "results": data,
    }


@app.get("/api/evaluations/raw")
def get_evaluation_raw(
    scenario: str = Query("eval_heldout_medium_301", description="Scenario identifier")
) -> List[Dict[str, Any]]:
    """Return raw per-run evaluation records for all seeds in a scenario."""
    if scenario not in VALID_SCENARIOS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scenario. Allowed: {list(VALID_SCENARIOS.keys())}",
        )

    raw_path = os.path.join(_PROJECT_ROOT, "results", scenario, "evaluation_raw_results.json")
    if not os.path.exists(raw_path):
        raise HTTPException(status_code=404, detail=f"Raw results not found for scenario {scenario}.")

    with open(raw_path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/evaluations/comparison")
def get_cross_scenario_comparison() -> Dict[str, Any]:
    """Return aggregated cross-scenario metrics comparing all three controllers."""
    controllers = ["FixedTimeController", "ActuatedController", "PPOController"]
    metrics = [
        "mean_waiting_time_seconds",
        "mean_queue_vehicles",
        "total_stops",
        "total_emissions_mg",
        "total_reward",
        "phase_switches",
        "total_throughput_vehicles",
    ]

    scenario_data: Dict[str, Any] = {}
    for sc_id, sc_info in VALID_SCENARIOS.items():
        summary_path = os.path.join(_PROJECT_ROOT, "results", sc_id, "evaluation_summary.json")
        if os.path.exists(summary_path):
            with open(summary_path, "r", encoding="utf-8") as f:
                scenario_data[sc_id] = {
                    "info": sc_info,
                    "summary": json.load(f),
                }

    return {
        "controllers": controllers,
        "metrics": metrics,
        "scenarios": scenario_data,
    }


class SimulationRunRequest(BaseModel):
    controller_type: str = Field(..., description="FixedTime, Actuated, or PPO")
    scenario: str = Field("eval_heldout_medium_301", description="Scenario ID")
    seed: int = Field(301, description="Random seed")
    max_steps: int = Field(120, ge=10, le=300, description="Max simulation steps")


@app.post("/api/simulation/run")
def run_live_simulation(req: SimulationRunRequest) -> Dict[str, Any]:
    """Execute an authentic SUMO TraCI simulation episode and return step telemetry.

    Executes a real headless SUMO episode using the specified controller policy and
    held-out scenario route file. SignalTransitionManager strictly enforces all safety
    guardrails (min green 5s, yellow clearance 3s, max green 45s).

    Args:
        req: SimulationRunRequest specifying:
            - controller_type: 'FixedTime', 'Actuated', or 'PPO'.
            - scenario: Valid held-out scenario ID.
            - seed: Random seed for vehicle insertion and route dynamics.
            - max_steps: Decision steps to execute (10 to 300).

    Returns:
        Dict[str, Any] containing:
            - success: True upon successful episode completion.
            - controller: Controller type executed.
            - scenario: Scenario identifier.
            - seed: Simulation seed.
            - summary: Aggregated metrics (mean waiting time, queues, emissions, reward).
            - step_records: Step-by-step telemetry list for scrubbing and inspection.

    Raises:
        HTTPException(400): If scenario or controller_type is invalid.
        HTTPException(404): If PPO checkpoint is requested but missing on disk.
        HTTPException(500): If SUMO/TraCI raises an unhandled simulation error.
    """
    if req.scenario not in VALID_SCENARIOS:
        raise HTTPException(status_code=400, detail="Invalid scenario identifier.")

    ctrl_type = req.controller_type.strip()
    if ctrl_type not in {"FixedTime", "Actuated", "PPO"}:
        raise HTTPException(
            status_code=400,
            detail="Invalid controller_type. Must be 'FixedTime', 'Actuated', or 'PPO'.",
        )

    from evaluation.evaluate_all import build_evaluation_config, make_eval_environment
    from evaluation.runner import run_simulation_experiment
    from controllers.fixed_time import FixedTimeController
    from controllers.actuated import ActuatedController
    from controllers.ppo import PPOController

    cfg = build_evaluation_config()
    route_file = os.path.join(_PROJECT_ROOT, VALID_SCENARIOS[req.scenario]["route_file"])
    model_path = os.path.join(_PROJECT_ROOT, "models", "ppo_production", "ppo_traffic_final.zip")

    if ctrl_type == "FixedTime":
        controller = FixedTimeController.from_config(cfg, default_green_seconds=42.0)
    elif ctrl_type == "Actuated":
        controller = ActuatedController.from_config(cfg, queue_threshold=0.5)
    elif ctrl_type == "PPO":
        if not os.path.exists(model_path):
            raise HTTPException(status_code=404, detail="PPO model checkpoint not found.")
        controller = PPOController(model_path, deterministic=True)

    env = make_eval_environment(route_file=route_file, max_steps=req.max_steps)

    try:
        exp_res = run_simulation_experiment(
            env=env,
            controller=controller,
            seed=req.seed,
            max_steps=req.max_steps,
            close_env=True,
        )
        return {
            "success": True,
            "controller": ctrl_type,
            "scenario": req.scenario,
            "seed": req.seed,
            "summary": exp_res.summary(),
            "step_records": [s.to_dict() for s in exp_res.step_records],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Simulation error: {exc}")
    finally:
        try:
            env.close()
        except Exception:
            pass


# Mount static production build if available
frontend_dist = os.path.join(_PROJECT_ROOT, "frontend", "dist")
if os.path.exists(frontend_dist):
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True, app_dir=_PROJECT_ROOT)
