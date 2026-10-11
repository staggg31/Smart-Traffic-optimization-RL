"""Experiment runner and evaluation metrics recorder for traffic signal controllers.

This module provides reproducible experiment execution and metrics aggregation
for evaluating traffic signal controllers against the SUMO environment wrapper.
It records simulator measurements with distinction between measured zero values
and unavailable metrics (such as throughput when exit lanes are not configured).
"""

from dataclasses import asdict, dataclass
import math
from typing import Any, Dict, List, Optional
import numpy as np

from controllers.base import BaseTrafficController
from environment.sumo_environment import SumoEnvironment


@dataclass(frozen=True)
class StepRecord:
    """Individual simulation step telemetry record."""

    step: int
    simulation_time: float
    action: int
    active_green_phase: int
    reward: float
    waiting_time_seconds: float
    queue_vehicles: float
    stops: int
    emissions_mg: float
    throughput: Optional[float]
    clearance_executed: bool
    clearance_duration_seconds: float
    clearance_phases: List[int]

    def to_dict(self) -> Dict[str, Any]:
        """Convert step record to dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class ExperimentResult:
    """Comprehensive aggregated experiment result."""

    controller_name: str
    total_steps: int
    simulation_time_seconds: float
    total_reward: float
    mean_waiting_time_seconds: float
    mean_queue_vehicles: float
    total_stops: int
    total_emissions_mg: float
    total_throughput_vehicles: Optional[float]
    throughput_available: bool
    terminated: bool
    truncated: bool
    phase_switches: int
    clearance_episodes: int
    step_records: List[StepRecord]

    def to_dict(self, include_step_records: bool = True) -> Dict[str, Any]:
        """Convert experiment result to dictionary."""
        data = asdict(self)
        if not include_step_records:
            data["step_records"] = []
        return data

    def summary(self) -> Dict[str, Any]:
        """Summary metrics dictionary omitting detailed step records."""
        return self.to_dict(include_step_records=False)


def run_simulation_experiment(
    env: SumoEnvironment,
    controller: BaseTrafficController,
    seed: Optional[int] = None,
    max_steps: Optional[int] = None,
    close_env: bool = False,
) -> ExperimentResult:
    """Execute a controlled simulation experiment and record comprehensive metrics.

    Args:
        env: Active or initialized SumoEnvironment instance.
        controller: BaseTrafficController implementation to evaluate.
        seed: Optional random seed passed to environment reset.
        max_steps: Optional maximum number of control steps to execute.
            If None, executes until environment terminates or truncates naturally.
        close_env: Whether to automatically close the environment upon completion.

    Returns:
        ExperimentResult containing aggregated performance metrics and step records.

    Raises:
        ValueError: If max_steps is invalid.
    """
    if max_steps is not None:
        if (
            isinstance(max_steps, bool)
            or not isinstance(max_steps, int)
            or max_steps < 0
        ):
            raise ValueError(f"max_steps must be a non-negative integer, got {max_steps!r}.")

    controller.reset()

    try:
        obs, reset_info = env.reset(seed=seed)
        throughput_available = bool(reset_info.get("throughput_tracking_active", False))

        step_records: List[StepRecord] = []
        total_reward: float = 0.0
        waiting_times: List[float] = []
        queue_lengths: List[float] = []
        total_stops: int = 0
        total_emissions_mg: float = 0.0
        cumulative_throughput: float = 0.0
        phase_switches: int = 0
        clearance_episodes: int = 0

        terminated: bool = False
        truncated: bool = False
        current_green: int = int(reset_info.get("active_green_phase", 0))

        while True:
            if max_steps is not None and len(step_records) >= max_steps:
                truncated = True
                break

            action = controller.act(obs)
            next_obs, reward, terminated, truncated, info = env.step(action)

            # Extract step metrics
            raw_metrics = info.get("raw_metrics")
            if raw_metrics is not None:
                step_wait = float(raw_metrics.accumulated_waiting_time_seconds)
                step_queue = float(raw_metrics.queue_vehicles)
                step_stops = int(raw_metrics.stops_count)
                step_emiss = float(raw_metrics.emissions_total_mg)
                step_thru = float(raw_metrics.throughput_vehicles)
            else:
                step_wait = 0.0
                step_queue = 0.0
                step_stops = 0
                step_emiss = 0.0
                step_thru = 0.0

            clearance_exec = bool(info.get("clearance_executed", False))
            clearance_dur = float(info.get("clearance_duration_seconds", 0.0))
            clearance_phs = list(info.get("clearance_phases", []))
            active_green = int(info.get("active_green_phase", current_green))

            if clearance_exec:
                clearance_episodes += 1

            if active_green != current_green:
                phase_switches += 1
                current_green = active_green

            total_reward += float(reward)
            waiting_times.append(step_wait)
            queue_lengths.append(step_queue)
            total_stops += step_stops
            total_emissions_mg += step_emiss

            if throughput_available:
                cumulative_throughput += step_thru
                step_thru_val: Optional[float] = step_thru
            else:
                step_thru_val = None

            record = StepRecord(
                step=int(info.get("step", len(step_records) + 1)),
                simulation_time=float(info.get("simulation_time", 0.0)),
                action=int(action),
                active_green_phase=active_green,
                reward=float(reward),
                waiting_time_seconds=step_wait,
                queue_vehicles=step_queue,
                stops=step_stops,
                emissions_mg=step_emiss,
                throughput=step_thru_val,
                clearance_executed=clearance_exec,
                clearance_duration_seconds=clearance_dur,
                clearance_phases=clearance_phs,
            )
            step_records.append(record)

            obs = next_obs
            if terminated or truncated:
                break

        num_steps = len(step_records)
        mean_wait = float(np.mean(waiting_times)) if num_steps > 0 else 0.0
        mean_queue = float(np.mean(queue_lengths)) if num_steps > 0 else 0.0
        sim_time = step_records[-1].simulation_time if num_steps > 0 else float(reset_info.get("simulation_time", 0.0))
        final_throughput = cumulative_throughput if throughput_available else None

        return ExperimentResult(
            controller_name=controller.__class__.__name__,
            total_steps=num_steps,
            simulation_time_seconds=sim_time,
            total_reward=total_reward,
            mean_waiting_time_seconds=mean_wait,
            mean_queue_vehicles=mean_queue,
            total_stops=total_stops,
            total_emissions_mg=total_emissions_mg,
            total_throughput_vehicles=final_throughput,
            throughput_available=throughput_available,
            terminated=terminated,
            truncated=truncated,
            phase_switches=phase_switches,
            clearance_episodes=clearance_episodes,
            step_records=step_records,
        )

    finally:
        if close_env:
            env.close()
