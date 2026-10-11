"""Fixed-time baseline traffic signal controller.

This module provides a deterministic fixed-time controller that cycles through
pre-configured green phases according to fixed duration schedules, implementing the
canonical BaseTrafficController interface.
"""

import math
from typing import Dict, List, Optional
import numpy as np

from config.schema import IntersectionConfig
from controllers.base import BaseTrafficController


class FixedTimeController(BaseTrafficController):
    """Deterministic fixed-time cyclic traffic signal controller.

    Decoupling & Safety Contract:
        1. Emits abstract action indices corresponding to green phase candidates.
        2. Never commands raw SUMO phases or TraCI commands directly.
        3. All phase transitions, clearance intervals (yellow / all-red), and
           minimum-green constraints are enforced by the environment and its
           safety transition manager.
        4. Cycles through `phase_sequence` holding each action for its assigned
           duration before signaling a switch to the next candidate.
    """

    def __init__(
        self,
        phase_durations: Dict[int, float],
        control_interval_seconds: float = 1.0,
        phase_sequence: Optional[List[int]] = None,
    ) -> None:
        """Initialize fixed-time controller with validated durations and sequence.

        Args:
            phase_durations: Mapping of `action_index -> green_duration_seconds`.
                All action indices must be non-negative integers; durations must be
                positive finite numbers.
            control_interval_seconds: Time advancement per controller decision point.
                Must be a positive finite number. Defaults to 1.0.
            phase_sequence: Optional cyclic ordering of action indices. If None,
                defaults to sorted keys of `phase_durations`.
        """
        if not isinstance(phase_durations, dict) or len(phase_durations) == 0:
            raise ValueError("phase_durations must be a non-empty dictionary.")

        self._phase_durations: Dict[int, float] = {}
        for action_idx, duration in phase_durations.items():
            if (
                isinstance(action_idx, bool)
                or not isinstance(action_idx, int)
                or action_idx < 0
            ):
                raise ValueError(
                    f"Action index must be a non-negative integer, got {action_idx!r}."
                )
            if (
                isinstance(duration, bool)
                or not isinstance(duration, (int, float))
                or not math.isfinite(duration)
                or duration <= 0
            ):
                raise ValueError(
                    f"Duration for action {action_idx} must be a positive finite number, got {duration!r}."
                )
            self._phase_durations[action_idx] = float(duration)

        if (
            isinstance(control_interval_seconds, bool)
            or not isinstance(control_interval_seconds, (int, float))
            or not math.isfinite(control_interval_seconds)
            or control_interval_seconds <= 0
        ):
            raise ValueError(
                f"control_interval_seconds must be a positive finite number, got {control_interval_seconds!r}."
            )
        self._control_interval_seconds: float = float(control_interval_seconds)

        if phase_sequence is not None:
            if not isinstance(phase_sequence, list) or len(phase_sequence) == 0:
                raise ValueError("phase_sequence must be a non-empty list of action indices.")
            for act in phase_sequence:
                if act not in self._phase_durations:
                    raise ValueError(
                        f"Action {act!r} in phase_sequence is not defined in phase_durations."
                    )
            self._phase_sequence: List[int] = list(phase_sequence)
        else:
            self._phase_sequence = sorted(self._phase_durations.keys())

        # State tracking
        self._sequence_index: int = 0
        self._elapsed_in_phase: float = 0.0

    @classmethod
    def from_config(
        cls,
        config: IntersectionConfig,
        default_green_seconds: float = 42.0,
        phase_durations_override: Optional[Dict[int, float]] = None,
    ) -> "FixedTimeController":
        """Construct a FixedTimeController from an IntersectionConfig.

        Args:
            config: Validated IntersectionConfig instance.
            default_green_seconds: Default duration for all green phases if not overridden.
            phase_durations_override: Optional custom duration mapping per action index.

        Returns:
            FixedTimeController instance.
        """
        num_actions = len(config.green_phase_indices)
        if phase_durations_override is not None:
            durations = dict(phase_durations_override)
        else:
            durations = {i: float(default_green_seconds) for i in range(num_actions)}

        return cls(
            phase_durations=durations,
            control_interval_seconds=config.control_interval_seconds,
            phase_sequence=list(range(num_actions)),
        )

    @property
    def current_action(self) -> int:
        """The currently active abstract controller action index."""
        return self._phase_sequence[self._sequence_index]

    @property
    def elapsed_in_phase(self) -> float:
        """Elapsed time in seconds since the current green action was initiated."""
        return self._elapsed_in_phase

    @property
    def phase_durations(self) -> Dict[int, float]:
        """Configured phase durations mapping `action -> duration_seconds`."""
        return dict(self._phase_durations)

    @property
    def phase_sequence(self) -> List[int]:
        """Configured cyclical action sequence."""
        return list(self._phase_sequence)

    @property
    def control_interval_seconds(self) -> float:
        """Decision time interval in seconds."""
        return self._control_interval_seconds

    def act(self, observation: np.ndarray) -> int:
        """Select abstract action index according to the fixed-time schedule.

        Args:
            observation: Numerical state vector from the environment.

        Returns:
            int: Discrete action index.

        Raises:
            ValueError: If observation is not a valid finite numpy array.
        """
        if not isinstance(observation, np.ndarray):
            raise ValueError(f"observation must be a numpy.ndarray, got {type(observation)!r}.")
        if observation.ndim != 1:
            raise ValueError(f"observation must be a 1D array, got shape {observation.shape}.")
        if not np.all(np.isfinite(observation)):
            raise ValueError("observation contains non-finite values (NaN or Inf).")

        current_action = self._phase_sequence[self._sequence_index]
        target_duration = self._phase_durations[current_action]

        # Advance timer for the current interval
        self._elapsed_in_phase += self._control_interval_seconds

        # If phase duration has expired, switch to the next action in sequence
        if self._elapsed_in_phase >= target_duration - 1e-6:
            self._sequence_index = (self._sequence_index + 1) % len(self._phase_sequence)
            self._elapsed_in_phase = 0.0

        return current_action

    def reset(self) -> None:
        """Reset internal timers and sequence pointer to initial phase."""
        self._sequence_index = 0
        self._elapsed_in_phase = 0.0
