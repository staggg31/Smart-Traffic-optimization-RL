"""Configuration schemas and data contracts for traffic signal control.

This module defines the configuration interface for signalized intersections.
It decouples network topology, detector definitions, and signal timings from
controller algorithms, avoiding hardcoded junction identifiers or phase numbers.
"""

from dataclasses import dataclass, field
import math
from typing import List, Optional


@dataclass(frozen=True)
class IntersectionConfig:
    """Configuration contract for a signalized intersection.

    Attributes:
        tls_id: Traffic light identifier defined in the SUMO network.
        incoming_lanes: List of incoming lane IDs feeding into the intersection.
        green_phase_indices: List of valid, non-conflicting green phase indices
            defined within the network's `tlLogic`.
        min_green_seconds: Minimum duration (in seconds) a green phase must be
            served before a phase transition can be initiated.
        max_green_seconds: Upper bound duration (in seconds) a green phase may be
            held, mitigating vehicle starvation on competing approaches.
        control_interval_seconds: Discrete time increment (in seconds) between
            controller decision points. Defaults to 1.0.
        yellow_seconds: Duration (in seconds) of yellow change intervals. Used
            only when clearance transitions are managed externally by the controller
            wrapper. Must NOT duplicate clearance phases already encoded in the
            validated SUMO `tlLogic`. Defaults to 0.0.
        all_red_seconds: Duration (in seconds) of all-red clearance intervals. Used
            only when clearance transitions are managed externally. Must NOT duplicate
            clearance phases already encoded in the validated SUMO `tlLogic`. Defaults to 0.0.
        clearance_handled_by_sumo: If True, intermediate yellow/red clearance
            phases are assumed to be managed internally by SUMO `tlLogic` or step
            transitions rather than manually scheduled by the external controller.
            Defaults to True.
    """

    tls_id: str
    incoming_lanes: List[str]
    green_phase_indices: List[int]
    min_green_seconds: float
    max_green_seconds: float
    control_interval_seconds: float = 1.0
    yellow_seconds: float = 0.0
    all_red_seconds: float = 0.0
    clearance_handled_by_sumo: bool = True
    exit_lanes: Optional[List[str]] = None

    def __post_init__(self) -> None:
        """Validate configuration parameters upon instantiation."""
        self.validate()

    def validate(self) -> None:
        """Verify the semantic validity and bounds of configuration fields.

        Raises:
            ValueError: If any field fails semantic or boundary validation.
        """
        # Validate TLS identifier
        if not isinstance(self.tls_id, str) or not self.tls_id.strip():
            raise ValueError("tls_id must be a non-empty string.")

        # Validate incoming lanes
        if not isinstance(self.incoming_lanes, list) or len(self.incoming_lanes) == 0:
            raise ValueError("incoming_lanes must be a non-empty list of lane IDs.")
        for lane in self.incoming_lanes:
            if not isinstance(lane, str) or not lane.strip():
                raise ValueError("All entries in incoming_lanes must be non-empty strings.")
        if len(self.incoming_lanes) != len(set(self.incoming_lanes)):
            raise ValueError("incoming_lanes contains duplicate lane identifiers.")

        # Validate exit lanes if provided
        if self.exit_lanes is not None:
            if not isinstance(self.exit_lanes, list) or len(self.exit_lanes) == 0:
                raise ValueError("exit_lanes must be a non-empty list of lane IDs when provided.")
            for lane in self.exit_lanes:
                if not isinstance(lane, str) or not lane.strip():
                    raise ValueError("All entries in exit_lanes must be non-empty strings.")
            if len(self.exit_lanes) != len(set(self.exit_lanes)):
                raise ValueError("exit_lanes contains duplicate lane identifiers.")

        # Validate green phase indices
        if not isinstance(self.green_phase_indices, list) or len(self.green_phase_indices) == 0:
            raise ValueError("green_phase_indices must be a non-empty list of phase indices.")
        for idx in self.green_phase_indices:
            if isinstance(idx, bool) or not isinstance(idx, int) or idx < 0:
                raise ValueError(f"Invalid phase index '{idx}'. Green phase indices must be non-negative integers.")
        if len(self.green_phase_indices) != len(set(self.green_phase_indices)):
            raise ValueError("green_phase_indices contains duplicate phase indices.")

        # Validate boolean flag
        if not isinstance(self.clearance_handled_by_sumo, bool):
            raise ValueError("clearance_handled_by_sumo must be a boolean.")

        # Validate timing fields: reject non-numbers, booleans, NaN, and infinities
        timing_fields = [
            ("min_green_seconds", self.min_green_seconds),
            ("max_green_seconds", self.max_green_seconds),
            ("control_interval_seconds", self.control_interval_seconds),
            ("yellow_seconds", self.yellow_seconds),
            ("all_red_seconds", self.all_red_seconds),
        ]
        for name, val in timing_fields:
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
                raise ValueError(f"{name} must be a finite real number, got {val!r}.")

        # Validate timing bounds
        if self.min_green_seconds <= 0:
            raise ValueError(
                f"min_green_seconds must be positive, got {self.min_green_seconds}."
            )
        if self.max_green_seconds <= 0:
            raise ValueError(
                f"max_green_seconds must be positive, got {self.max_green_seconds}."
            )
        if self.max_green_seconds < self.min_green_seconds:
            raise ValueError(
                f"max_green_seconds ({self.max_green_seconds}) cannot be less than "
                f"min_green_seconds ({self.min_green_seconds})."
            )
        if self.control_interval_seconds <= 0:
            raise ValueError(
                f"control_interval_seconds must be positive, got {self.control_interval_seconds}."
            )
        if self.yellow_seconds < 0:
            raise ValueError(
                f"yellow_seconds must be non-negative, got {self.yellow_seconds}."
            )
        if self.all_red_seconds < 0:
            raise ValueError(
                f"all_red_seconds must be non-negative, got {self.all_red_seconds}."
            )
