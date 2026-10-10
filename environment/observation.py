"""Observation interface and deterministic observation vector builder.

This module provides data structures and builder logic to convert raw intersection
measurements into deterministic numerical observation vectors for reinforcement
learning agents. It operates purely on validated numerical inputs and remains
completely decoupled from TraCI or specific intersection network topologies.
"""

from dataclasses import dataclass
import math
from typing import Dict, List, Optional
import numpy as np


@dataclass(frozen=True)
class LaneMeasurement:
    """Raw physical measurements for an approach lane at control step k.

    Attributes:
        queue_length_vehicles: Count of halted vehicles (speed < 0.1 m/s) on the lane (>= 0).
        vehicle_count: Total count of vehicles occupying the lane (>= 0).
        accumulated_waiting_time_seconds: Sum of accumulated waiting times of all
            currently halted vehicles on the lane (seconds >= 0).
        average_speed_mps: Space-mean speed of vehicles currently on the lane (m/s >= 0).
    """

    queue_length_vehicles: float
    vehicle_count: float
    accumulated_waiting_time_seconds: float
    average_speed_mps: float

    def __post_init__(self) -> None:
        """Validate lane measurement fields."""
        fields = [
            ("queue_length_vehicles", self.queue_length_vehicles),
            ("vehicle_count", self.vehicle_count),
            ("accumulated_waiting_time_seconds", self.accumulated_waiting_time_seconds),
            ("average_speed_mps", self.average_speed_mps),
        ]
        for name, val in fields:
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
                raise ValueError(f"{name} must be a finite real number, got {val!r}.")
            if val < 0.0:
                raise ValueError(f"{name} must be non-negative, got {val}.")


@dataclass(frozen=True)
class IntersectionMeasurement:
    """Snapshot of raw physical measurements across the intersection.

    Attributes:
        lane_measurements: Mapping of lane_id -> LaneMeasurement.
        current_green_phase: Currently active green phase index.
        elapsed_green_seconds: Continuous duration current green has been active (seconds >= 0).
        min_green_satisfied: Boolean flag indicating if minimum green duration has elapsed.
    """

    lane_measurements: Dict[str, LaneMeasurement]
    current_green_phase: int
    elapsed_green_seconds: float
    min_green_satisfied: bool

    def __post_init__(self) -> None:
        """Validate intersection measurement fields."""
        if not isinstance(self.lane_measurements, dict) or len(self.lane_measurements) == 0:
            raise ValueError("lane_measurements must be a non-empty dictionary.")
        for k, v in self.lane_measurements.items():
            if not isinstance(k, str) or not k.strip():
                raise ValueError("All lane keys in lane_measurements must be non-empty strings.")
            if not isinstance(v, LaneMeasurement):
                raise ValueError(f"Measurement for lane {k!r} must be a LaneMeasurement instance.")

        if (
            isinstance(self.current_green_phase, bool)
            or not isinstance(self.current_green_phase, int)
            or self.current_green_phase < 0
        ):
            raise ValueError(f"current_green_phase must be a non-negative integer, got {self.current_green_phase!r}.")

        if (
            isinstance(self.elapsed_green_seconds, bool)
            or not isinstance(self.elapsed_green_seconds, (int, float))
            or not math.isfinite(self.elapsed_green_seconds)
            or self.elapsed_green_seconds < 0.0
        ):
            raise ValueError(f"elapsed_green_seconds must be a non-negative finite real number, got {self.elapsed_green_seconds!r}.")

        if not isinstance(self.min_green_satisfied, bool):
            raise ValueError(f"min_green_satisfied must be a boolean, got {self.min_green_satisfied!r}.")


@dataclass(frozen=True)
class ObservationNormalizerConfig:
    """Explicit reference scales for normalizing observation vector features.

    All scales represent physical upper bounds or nominal maximums and must be
    explicitly provided. Values are normalized as `x_norm = clip(x / scale, 0.0, 1.0)`.

    Attributes:
        max_queue_per_lane: Physical vehicle storage capacity of incoming lane (vehicles > 0).
        max_vehicles_per_lane: Maximum vehicle capacity of incoming lane (vehicles > 0).
        max_waiting_time_seconds: Reference threshold for accumulated wait time (seconds > 0).
        speed_limit_mps: Approach lane speed limit in meters per second (m/s > 0).
        max_green_seconds: Maximum allowed green time before forced progression (seconds > 0).
    """

    max_queue_per_lane: float
    max_vehicles_per_lane: float
    max_waiting_time_seconds: float
    speed_limit_mps: float
    max_green_seconds: float

    def __post_init__(self) -> None:
        """Validate normalizer configuration parameters."""
        fields = [
            ("max_queue_per_lane", self.max_queue_per_lane),
            ("max_vehicles_per_lane", self.max_vehicles_per_lane),
            ("max_waiting_time_seconds", self.max_waiting_time_seconds),
            ("speed_limit_mps", self.speed_limit_mps),
            ("max_green_seconds", self.max_green_seconds),
        ]
        for name, val in fields:
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
                raise ValueError(f"{name} must be a finite real number, got {val!r}.")
            if val <= 0.0:
                raise ValueError(f"{name} must be strictly positive, got {val}.")


class ObservationBuilder:
    """Builds a deterministic 1D float32 observation vector from an IntersectionMeasurement.

    Vector Layout Specification:
        Let L = number of ordered incoming lanes, P = number of ordered green phases.
        Total observation vector dimension = 4 * L + P + 2.

        1. Indices [0 : L]: Queue lengths for each lane in `lane_order`.
        2. Indices [L : 2L]: Vehicle counts for each lane in `lane_order`.
        3. Indices [2L : 3L]: Accumulated waiting times for each lane in `lane_order`.
        4. Indices [3L : 4L]: Average speeds for each lane in `lane_order`.
        5. Indices [4L : 4L + P]: One-hot vector of length P corresponding to `green_phase_order`.
        6. Index [4L + P]: Elapsed green duration (scalar).
        7. Index [4L + P + 1]: Min-green satisfied indicator (binary 0.0 or 1.0).

    Operational Modes:
        - Raw Mode (`normalizer_config is None`): Features are stored in their native
          physical units (counts, seconds, m/s).
        - Normalized Mode (`normalizer_config is not None`): Features are divided by
          their respective scale and clipped to [0.0, 1.0].
    """

    def __init__(
        self,
        lane_order: List[str],
        green_phase_order: List[int],
        normalizer_config: Optional[ObservationNormalizerConfig] = None,
    ) -> None:
        """Initialize observation builder with canonical ordering and optional scales.

        Args:
            lane_order: List of lane identifiers defining the canonical ordering.
            green_phase_order: List of green phase indices defining the canonical one-hot order.
            normalizer_config: Optional scaling parameters for normalization.
        """
        if not isinstance(lane_order, list) or len(lane_order) == 0:
            raise ValueError("lane_order must be a non-empty list of lane IDs.")
        for lane in lane_order:
            if not isinstance(lane, str) or not lane.strip():
                raise ValueError("All entries in lane_order must be non-empty strings.")
        if len(lane_order) != len(set(lane_order)):
            raise ValueError("lane_order contains duplicate lane identifiers.")

        if not isinstance(green_phase_order, list) or len(green_phase_order) == 0:
            raise ValueError("green_phase_order must be a non-empty list of phase indices.")
        for idx in green_phase_order:
            if isinstance(idx, bool) or not isinstance(idx, int) or idx < 0:
                raise ValueError(f"Invalid phase index {idx!r} in green_phase_order.")
        if len(green_phase_order) != len(set(green_phase_order)):
            raise ValueError("green_phase_order contains duplicate phase indices.")

        if normalizer_config is not None and not isinstance(normalizer_config, ObservationNormalizerConfig):
            raise ValueError("normalizer_config must be an ObservationNormalizerConfig instance or None.")

        self._lane_order: List[str] = list(lane_order)
        self._green_phase_order: List[int] = list(green_phase_order)
        self._normalizer: Optional[ObservationNormalizerConfig] = normalizer_config

    @property
    def lane_order(self) -> List[str]:
        """Canonical ordered list of lane IDs."""
        return list(self._lane_order)

    @property
    def green_phase_order(self) -> List[int]:
        """Canonical ordered list of green phase indices."""
        return list(self._green_phase_order)

    @property
    def vector_dim(self) -> int:
        """Total dimension of the constructed observation vector."""
        return 4 * len(self._lane_order) + len(self._green_phase_order) + 2

    @property
    def is_normalized(self) -> bool:
        """True if the builder scales features to [0.0, 1.0]."""
        return self._normalizer is not None

    def build(self, measurement: IntersectionMeasurement) -> np.ndarray:
        """Construct a deterministic 1D float32 observation vector.

        Args:
            measurement: Validated IntersectionMeasurement instance.

        Returns:
            np.ndarray of shape (vector_dim,) and dtype float32.

        Raises:
            KeyError: If any lane in `lane_order` is missing from `measurement.lane_measurements`.
            ValueError: If `measurement.current_green_phase` is not in `green_phase_order`.
        """
        if not isinstance(measurement, IntersectionMeasurement):
            raise ValueError(f"measurement must be an IntersectionMeasurement, got {measurement!r}.")

        # Check for exact lane set match (no missing and no unexpected lanes)
        measurement_lanes = set(measurement.lane_measurements.keys())
        expected_lanes = set(self._lane_order)
        missing_lanes = [lane for lane in self._lane_order if lane not in measurement_lanes]
        if missing_lanes:
            raise KeyError(f"Measurement missing required lane(s): {missing_lanes}.")
        unexpected_lanes = sorted(measurement_lanes - expected_lanes)
        if unexpected_lanes:
            raise ValueError(f"Measurement contains unexpected lane(s) not in lane_order: {unexpected_lanes}.")

        # Check green phase is recognized
        if measurement.current_green_phase not in self._green_phase_order:
            raise ValueError(
                f"Active phase {measurement.current_green_phase} is not in green_phase_order {self._green_phase_order}."
            )

        queues: List[float] = []
        counts: List[float] = []
        waits: List[float] = []
        speeds: List[float] = []

        norm = self._normalizer

        for lane_id in self._lane_order:
            m = measurement.lane_measurements[lane_id]
            if norm is not None:
                q = min(1.0, max(0.0, m.queue_length_vehicles / norm.max_queue_per_lane))
                c = min(1.0, max(0.0, m.vehicle_count / norm.max_vehicles_per_lane))
                w = min(1.0, max(0.0, m.accumulated_waiting_time_seconds / norm.max_waiting_time_seconds))
                s = min(1.0, max(0.0, m.average_speed_mps / norm.speed_limit_mps))
            else:
                q = m.queue_length_vehicles
                c = m.vehicle_count
                w = m.accumulated_waiting_time_seconds
                s = m.average_speed_mps

            queues.append(q)
            counts.append(c)
            waits.append(w)
            speeds.append(s)

        # One-hot phase vector
        one_hot = [
            1.0 if p == measurement.current_green_phase else 0.0
            for p in self._green_phase_order
        ]

        # Elapsed green time
        if norm is not None:
            elapsed = min(1.0, max(0.0, measurement.elapsed_green_seconds / norm.max_green_seconds))
        else:
            elapsed = measurement.elapsed_green_seconds

        # Min-green satisfied flag (binary 0.0 or 1.0)
        min_green_flag = 1.0 if measurement.min_green_satisfied else 0.0

        vector = queues + counts + waits + speeds + one_hot + [elapsed, min_green_flag]

        # Guard against float32 overflow
        for i, val in enumerate(vector):
            if not math.isfinite(val):
                raise ValueError(f"Feature at index {i} is not finite ({val!r}).")

        arr = np.array(vector, dtype=np.float32)
        if not np.all(np.isfinite(arr)):
            raise ValueError("Observation vector contains non-finite float32 values after conversion (overflow detected).")

        return arr
