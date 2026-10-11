"""Vehicle-actuated traffic signal controller with gap-out and max-green logic.

This module provides a vehicle-actuated controller baseline that dynamically extends
green time when approaching vehicles are detected, switching phases upon gap-out
(no vehicle within the extension gap) or max-green timeout.
All action indices correspond to abstract controller actions. Physical clearance
transitions and min-green guardrails remain strictly managed by the environment wrapper
and transition manager.
"""

import math
from typing import Dict, List, Optional, Tuple
import numpy as np

from config.schema import IntersectionConfig
from controllers.base import BaseTrafficController


class ActuatedController(BaseTrafficController):
    """Vehicle-actuated adaptive traffic signal controller.

    Safety & Architectural Contract:
        1. Emits discrete abstract action indices (green candidates).
        2. Never commands raw SUMO phases or calls TraCI directly.
        3. Respects minimum green and maximum green constraints.
        4. Monitors queue lengths and vehicle counts on incoming lanes associated
           with the active green phase.
        5. Extends green if traffic demand persists on active lanes;
           signals switch (requests conflicting phase) if active approach gaps out
           or reaches maximum green duration.
        6. Resets internal timers and state cleanly between episodes.
    """

    def __init__(
        self,
        num_actions: int,
        action_to_lanes: Dict[int, List[int]],
        min_green_seconds: float = 5.0,
        max_green_seconds: float = 45.0,
        control_interval_seconds: float = 1.0,
        num_lanes: int = 8,
        queue_threshold: float = 0.5,
        phase_sequence: Optional[List[int]] = None,
    ) -> None:
        """Initialize ActuatedController with lane-to-phase mapping and timing rules.

        Args:
            num_actions: Number of distinct green actions (e.g. 2 for N-S and E-W).
            action_to_lanes: Mapping from action index to list of lane indices in observation.
                For each lane index `i`, observation contains queue at `i` and count at `L + i`.
            min_green_seconds: Minimum duration (seconds) to hold green before gap-out can trigger.
            max_green_seconds: Maximum duration (seconds) to hold green before forced termination.
            control_interval_seconds: Time delta per decision step in seconds.
            num_lanes: Total number of incoming lanes in the observation vector.
            queue_threshold: Vehicle / queue threshold below which approach is considered gapped out.
            phase_sequence: Optional sequence of actions to cycle through upon gap-out.
        """
        if (
            isinstance(num_actions, bool)
            or not isinstance(num_actions, int)
            or num_actions <= 0
        ):
            raise ValueError(f"num_actions must be a positive integer, got {num_actions!r}.")

        if not isinstance(action_to_lanes, dict) or len(action_to_lanes) == 0:
            raise ValueError("action_to_lanes must be a non-empty dictionary.")

        for act, lanes in action_to_lanes.items():
            if isinstance(act, bool) or not isinstance(act, int) or act < 0 or act >= num_actions:
                raise ValueError(f"Action index {act!r} must be in range [0, {num_actions - 1}].")
            if not isinstance(lanes, list) or len(lanes) == 0:
                raise ValueError(f"Lanes for action {act} must be a non-empty list of integers.")
            for lane_idx in lanes:
                if (
                    isinstance(lane_idx, bool)
                    or not isinstance(lane_idx, int)
                    or lane_idx < 0
                    or lane_idx >= num_lanes
                ):
                    raise ValueError(f"Lane index {lane_idx!r} must be in range [0, {num_lanes - 1}].")

        if (
            isinstance(min_green_seconds, bool)
            or not isinstance(min_green_seconds, (int, float))
            or not math.isfinite(min_green_seconds)
            or min_green_seconds <= 0
        ):
            raise ValueError(f"min_green_seconds must be positive finite number, got {min_green_seconds!r}.")

        if (
            isinstance(max_green_seconds, bool)
            or not isinstance(max_green_seconds, (int, float))
            or not math.isfinite(max_green_seconds)
            or max_green_seconds <= min_green_seconds
        ):
            raise ValueError(
                f"max_green_seconds must be greater than min_green_seconds ({min_green_seconds}), got {max_green_seconds!r}."
            )

        if (
            isinstance(control_interval_seconds, bool)
            or not isinstance(control_interval_seconds, (int, float))
            or not math.isfinite(control_interval_seconds)
            or control_interval_seconds <= 0
        ):
            raise ValueError(f"control_interval_seconds must be positive finite number, got {control_interval_seconds!r}.")

        if (
            isinstance(num_lanes, bool)
            or not isinstance(num_lanes, int)
            or num_lanes <= 0
        ):
            raise ValueError(f"num_lanes must be a positive integer, got {num_lanes!r}.")

        if (
            isinstance(queue_threshold, bool)
            or not isinstance(queue_threshold, (int, float))
            or not math.isfinite(queue_threshold)
            or queue_threshold < 0
        ):
            raise ValueError(f"queue_threshold must be non-negative finite number, got {queue_threshold!r}.")

        self._num_actions = num_actions
        self._action_to_lanes = {k: list(v) for k, v in action_to_lanes.items()}
        self._min_green_seconds = float(min_green_seconds)
        self._max_green_seconds = float(max_green_seconds)
        self._control_interval_seconds = float(control_interval_seconds)
        self._num_lanes = num_lanes
        self._queue_threshold = float(queue_threshold)

        if phase_sequence is not None:
            if not isinstance(phase_sequence, list) or len(phase_sequence) == 0:
                raise ValueError("phase_sequence must be a non-empty list.")
            for act in phase_sequence:
                if act not in self._action_to_lanes:
                    raise ValueError(f"Action {act!r} in phase_sequence is not in action_to_lanes.")
            self._phase_sequence = list(phase_sequence)
        else:
            self._phase_sequence = sorted(self._action_to_lanes.keys())

        # State tracking
        self._sequence_index: int = 0
        self._current_action: int = self._phase_sequence[0]
        self._elapsed_in_phase: float = 0.0

    @classmethod
    def from_config(
        cls,
        config: IntersectionConfig,
        queue_threshold: float = 0.5,
    ) -> "ActuatedController":
        """Factory method to instantiate ActuatedController from IntersectionConfig.

        Maps incoming lanes automatically to actions based on lane prefix or order.
        For standard 4-leg intersections with N, S, E, W incoming lanes:
            - Action 0: North and South lanes (N_*, S_*)
            - Action 1: East and West lanes (E_*, W_*)
        """
        num_actions = len(config.green_phase_indices)
        num_lanes = len(config.incoming_lanes)
        action_to_lanes: Dict[int, List[int]] = {}

        # If 2 green phases, check standard N/S vs E/W partitioning
        if num_actions == 2:
            ns_lanes = [
                i for i, lane in enumerate(config.incoming_lanes)
                if lane.startswith("N_") or lane.startswith("S_")
            ]
            ew_lanes = [
                i for i, lane in enumerate(config.incoming_lanes)
                if lane.startswith("E_") or lane.startswith("W_")
            ]
            if len(ns_lanes) > 0 and len(ew_lanes) > 0 and (len(ns_lanes) + len(ew_lanes) == num_lanes):
                action_to_lanes[0] = ns_lanes
                action_to_lanes[1] = ew_lanes
            else:
                # Fallback to even split
                mid = num_lanes // 2
                action_to_lanes[0] = list(range(0, mid))
                action_to_lanes[1] = list(range(mid, num_lanes))
        else:
            # Generic even partition
            lanes_per_act = max(1, num_lanes // num_actions)
            for a in range(num_actions):
                start = a * lanes_per_act
                end = (a + 1) * lanes_per_act if a < num_actions - 1 else num_lanes
                action_to_lanes[a] = list(range(start, end))

        return cls(
            num_actions=num_actions,
            action_to_lanes=action_to_lanes,
            min_green_seconds=config.min_green_seconds,
            max_green_seconds=config.max_green_seconds,
            control_interval_seconds=config.control_interval_seconds,
            num_lanes=num_lanes,
            queue_threshold=queue_threshold,
            phase_sequence=list(range(num_actions)),
        )

    @property
    def current_action(self) -> int:
        """The currently active abstract controller action index."""
        return self._current_action

    @property
    def elapsed_in_phase(self) -> float:
        """Elapsed time in seconds within the current phase decision window."""
        return self._elapsed_in_phase

    @property
    def min_green_seconds(self) -> float:
        """Configured minimum green time in seconds."""
        return self._min_green_seconds

    @property
    def max_green_seconds(self) -> float:
        """Configured maximum green time in seconds."""
        return self._max_green_seconds

    def act(self, observation: np.ndarray) -> int:
        """Select action based on current phase occupancy and elapsed green duration.

        Observation Layout:
            [0 : L] = Queues
            [L : 2L] = Vehicle counts
            [2L : 3L] = Wait times
            [3L : 4L] = Speeds
            [4L : 4L + P] = Active green phase one-hot
            [4L + P] = Elapsed green time
            [4L + P + 1] = Min-green satisfied (0.0 or 1.0)
        """
        if not isinstance(observation, np.ndarray):
            raise ValueError(f"observation must be a numpy.ndarray, got {type(observation)!r}.")
        if observation.ndim != 1:
            raise ValueError(f"observation must be a 1D array, got shape {observation.shape}.")
        if not np.all(np.isfinite(observation)):
            raise ValueError("observation contains non-finite values (NaN or Inf).")

        expected_min_dim = 4 * self._num_lanes + self._num_actions + 2
        if len(observation) < expected_min_dim:
            raise ValueError(
                f"observation length {len(observation)} is shorter than expected {expected_min_dim}."
            )

        # Increment internal elapsed green timer
        self._elapsed_in_phase += self._control_interval_seconds

        # Read min_green_satisfied flag directly from observation if available
        min_green_flag_idx = 4 * self._num_lanes + self._num_actions + 1
        min_green_satisfied = bool(observation[min_green_flag_idx] > 0.5)

        # If min green is not satisfied according to timer or observation flag, hold current green
        if not min_green_satisfied or self._elapsed_in_phase < self._min_green_seconds - 1e-6:
            return self._current_action

        # Check for maximum green force-off
        if self._elapsed_in_phase >= self._max_green_seconds - 1e-6:
            # Force switch to next action in sequence
            self._advance_phase()
            return self._current_action

        # Check vehicle occupancy / queue on active approach lanes
        active_lanes = self._action_to_lanes[self._current_action]
        active_demand = False
        for lane_idx in active_lanes:
            queue_val = observation[lane_idx]
            count_val = observation[self._num_lanes + lane_idx]
            if queue_val > self._queue_threshold or count_val > self._queue_threshold:
                active_demand = True
                break

        if active_demand:
            # Demand exists: extend green for active phase
            return self._current_action
        else:
            # Approach gapped out: switch to next phase
            self._advance_phase()
            return self._current_action

    def _advance_phase(self) -> None:
        """Switch internal target to next action in cyclic sequence."""
        self._sequence_index = (self._sequence_index + 1) % len(self._phase_sequence)
        self._current_action = self._phase_sequence[self._sequence_index]
        self._elapsed_in_phase = 0.0

    def reset(self) -> None:
        """Reset internal timers and sequence pointers to initial state."""
        self._sequence_index = 0
        self._current_action = self._phase_sequence[0]
        self._elapsed_in_phase = 0.0
