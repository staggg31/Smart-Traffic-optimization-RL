"""Multi-objective reward interface and calculation engine.

This module provides data structures and mathematical routines to compute multi-objective
scalar rewards and individual objective breakdowns for reinforcement learning controllers.

Semantic & Measurement Documentation:
    1. Accumulated Waiting Time vs. Interval Delay:
       - `accumulated_waiting_time_seconds`: Represents the snapshot sum of all seconds that
         vehicles currently halted (speed < 0.1 m/s) on approach lanes have spent waiting.
       - Delay (Interval Delay): Represents the cumulative travel-time loss incurred strictly
         during the elapsed control step delta_t relative to free-flow conditions.
       These two metrics reflect distinct physical concepts and must not be treated as
       interchangeable. The raw input metric in this module explicitly captures
       `accumulated_waiting_time_seconds`.
    2. Emission Semantics:
       - `emissions_total_mg`: Represents total milligrams emitted by vehicles during interval
         delta_t. If the simulator reports an instantaneous emission rate (e.g. mg/s),
         temporal integration over delta_t must be performed prior to passing the value to
         RawRewardMetrics.
    3. Travel Time:
       - Trip travel time is an episode-level completion metric (derived from SUMO `tripinfo-output`),
         not an instantaneous step-level reward signal. It is reserved for evaluation logging.
"""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class RawRewardMetrics:
    """Raw, unweighted physical metrics measured over control interval delta_t.

    Attributes:
        accumulated_waiting_time_seconds: Sum of waiting times accrued by currently
            halted vehicles on incoming lanes (seconds >= 0).
        queue_vehicles: Total count of halted vehicles across incoming lanes (count >= 0).
        stops_count: Number of vehicles that decelerated to a complete stop during delta_t (count >= 0).
        emissions_total_mg: Total tailpipe emissions during delta_t in milligrams (mg >= 0).
        throughput_vehicles: Number of vehicles completing passage through the intersection
            during delta_t (count >= 0).
    """

    accumulated_waiting_time_seconds: float
    queue_vehicles: float
    stops_count: float
    emissions_total_mg: float
    throughput_vehicles: float

    def __post_init__(self) -> None:
        """Validate raw reward metric fields."""
        fields = [
            ("accumulated_waiting_time_seconds", self.accumulated_waiting_time_seconds),
            ("queue_vehicles", self.queue_vehicles),
            ("stops_count", self.stops_count),
            ("emissions_total_mg", self.emissions_total_mg),
            ("throughput_vehicles", self.throughput_vehicles),
        ]
        for name, val in fields:
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
                raise ValueError(f"{name} must be a finite real number, got {val!r}.")
            if val < 0.0:
                raise ValueError(f"{name} must be non-negative, got {val}.")


@dataclass(frozen=True)
class RewardScalingConfig:
    """Explicit reference scales for normalizing raw reward components.

    Each metric is converted into a dimensionless quantity:
        hat{C} = raw_metric / ref_scale

    Attributes:
        waiting_time_ref_seconds: Reference scale for accumulated waiting time (seconds > 0).
        queue_ref_vehicles: Reference scale for halted vehicle queue (count > 0).
        stops_ref_vehicles: Reference scale for vehicle stop count (count > 0).
        emissions_ref_mg: Reference scale for emissions (mg > 0).
        throughput_ref_vehicles: Reference scale for throughput capacity (count > 0).
    """

    waiting_time_ref_seconds: float
    queue_ref_vehicles: float
    stops_ref_vehicles: float
    emissions_ref_mg: float
    throughput_ref_vehicles: float

    def __post_init__(self) -> None:
        """Validate reference scale parameters."""
        fields = [
            ("waiting_time_ref_seconds", self.waiting_time_ref_seconds),
            ("queue_ref_vehicles", self.queue_ref_vehicles),
            ("stops_ref_vehicles", self.stops_ref_vehicles),
            ("emissions_ref_mg", self.emissions_ref_mg),
            ("throughput_ref_vehicles", self.throughput_ref_vehicles),
        ]
        for name, val in fields:
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
                raise ValueError(f"{name} must be a finite real number, got {val!r}.")
            if val <= 0.0:
                raise ValueError(f"{name} must be strictly positive, got {val}.")


@dataclass(frozen=True)
class RewardWeights:
    """Provisional weighting factors for combining normalized reward components.

    Cost components (waiting time, queue, stops, emissions) are penalized negatively.
    Throughput is rewarded positively.

    Attributes:
        w_waiting_time: Weight for normalized waiting time (>= 0).
        w_queue: Weight for normalized queue length (>= 0).
        w_stops: Weight for normalized stops (>= 0).
        w_emissions: Weight for normalized emissions (>= 0).
        w_throughput: Weight for normalized throughput bonus (>= 0).
    """

    w_waiting_time: float = 1.0
    w_queue: float = 0.5
    w_stops: float = 0.0
    w_emissions: float = 0.0
    w_throughput: float = 0.0

    def __post_init__(self) -> None:
        """Validate reward weighting parameters."""
        fields = [
            ("w_waiting_time", self.w_waiting_time),
            ("w_queue", self.w_queue),
            ("w_stops", self.w_stops),
            ("w_emissions", self.w_emissions),
            ("w_throughput", self.w_throughput),
        ]
        for name, val in fields:
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
                raise ValueError(f"{name} must be a finite real number, got {val!r}.")
            if val < 0.0:
                raise ValueError(f"{name} must be non-negative, got {val}.")


@dataclass(frozen=True)
class RewardBreakdown:
    """Detailed multi-objective breakdown of scalar reward and individual components.

    Attributes:
        scalar_reward: The final scalar reward r_k passed to the RL optimization loss.
        normalized_waiting_time: Dimensionless waiting time component (>= 0).
        normalized_queue: Dimensionless queue component (>= 0).
        normalized_stops: Dimensionless stop component (>= 0).
        normalized_emissions: Dimensionless emission component (>= 0).
        normalized_throughput: Dimensionless throughput component (>= 0).
        raw_metrics: Complete preserved RawRewardMetrics instance.
    """

    scalar_reward: float
    normalized_waiting_time: float
    normalized_queue: float
    normalized_stops: float
    normalized_emissions: float
    normalized_throughput: float
    raw_metrics: RawRewardMetrics


class RewardCalculator:
    """Computes normalized components and composite scalar rewards.

    Formula:
        cost = (w_waiting_time * hat{C}_wait +
                w_queue * hat{C}_queue +
                w_stops * hat{C}_stops +
                w_emissions * hat{C}_emissions)
        bonus = w_throughput * hat{B}_throughput
        scalar_reward = -cost + bonus
    """

    def __init__(self, scales: RewardScalingConfig, weights: RewardWeights) -> None:
        """Initialize the reward calculator with validated scales and weights.

        Args:
            scales: Validated RewardScalingConfig instance.
            weights: Validated RewardWeights instance.
        """
        if not isinstance(scales, RewardScalingConfig):
            raise ValueError(f"scales must be a RewardScalingConfig instance, got {scales!r}.")
        if not isinstance(weights, RewardWeights):
            raise ValueError(f"weights must be a RewardWeights instance, got {weights!r}.")

        self._scales: RewardScalingConfig = scales
        self._weights: RewardWeights = weights

    @property
    def scales(self) -> RewardScalingConfig:
        """Configured reference scales."""
        return self._scales

    @property
    def weights(self) -> RewardWeights:
        """Configured provisional weighting factors."""
        return self._weights

    def calculate(self, metrics: RawRewardMetrics) -> RewardBreakdown:
        """Calculate the normalized components and scalar reward.

        Preserves all raw physical metrics regardless of whether specific weights are zero.

        Args:
            metrics: Validated RawRewardMetrics instance.

        Returns:
            RewardBreakdown containing normalized components and composite scalar reward.
        """
        if not isinstance(metrics, RawRewardMetrics):
            raise ValueError(f"metrics must be a RawRewardMetrics instance, got {metrics!r}.")

        norm_wait = metrics.accumulated_waiting_time_seconds / self._scales.waiting_time_ref_seconds
        norm_queue = metrics.queue_vehicles / self._scales.queue_ref_vehicles
        norm_stops = metrics.stops_count / self._scales.stops_ref_vehicles
        norm_emissions = metrics.emissions_total_mg / self._scales.emissions_ref_mg
        norm_throughput = metrics.throughput_vehicles / self._scales.throughput_ref_vehicles

        cost = (
            self._weights.w_waiting_time * norm_wait
            + self._weights.w_queue * norm_queue
            + self._weights.w_stops * norm_stops
            + self._weights.w_emissions * norm_emissions
        )
        bonus = self._weights.w_throughput * norm_throughput

        scalar_reward = -cost + bonus

        return RewardBreakdown(
            scalar_reward=scalar_reward,
            normalized_waiting_time=norm_wait,
            normalized_queue=norm_queue,
            normalized_stops=norm_stops,
            normalized_emissions=norm_emissions,
            normalized_throughput=norm_throughput,
            raw_metrics=metrics,
        )
