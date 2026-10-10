"""Unit tests for multi-objective reward calculation engine."""

import unittest

from environment.reward import (
    RawRewardMetrics,
    RewardBreakdown,
    RewardCalculator,
    RewardScalingConfig,
    RewardWeights,
)


class TestRawRewardMetrics(unittest.TestCase):
    """Test validation of RawRewardMetrics."""

    def test_valid_metrics(self) -> None:
        m = RawRewardMetrics(
            accumulated_waiting_time_seconds=150.0,
            queue_vehicles=8.0,
            stops_count=3.0,
            emissions_total_mg=1200.0,
            throughput_vehicles=4.0,
        )
        self.assertEqual(m.accumulated_waiting_time_seconds, 150.0)
        self.assertEqual(m.queue_vehicles, 8.0)
        self.assertEqual(m.stops_count, 3.0)
        self.assertEqual(m.emissions_total_mg, 1200.0)
        self.assertEqual(m.throughput_vehicles, 4.0)

    def test_negative_values_rejected(self) -> None:
        with self.assertRaises(ValueError):
            RawRewardMetrics(accumulated_waiting_time_seconds=-1.0, queue_vehicles=0.0, stops_count=0.0, emissions_total_mg=0.0, throughput_vehicles=0.0)
        with self.assertRaises(ValueError):
            RawRewardMetrics(accumulated_waiting_time_seconds=0.0, queue_vehicles=-1.0, stops_count=0.0, emissions_total_mg=0.0, throughput_vehicles=0.0)
        with self.assertRaises(ValueError):
            RawRewardMetrics(accumulated_waiting_time_seconds=0.0, queue_vehicles=0.0, stops_count=-1.0, emissions_total_mg=0.0, throughput_vehicles=0.0)
        with self.assertRaises(ValueError):
            RawRewardMetrics(accumulated_waiting_time_seconds=0.0, queue_vehicles=0.0, stops_count=0.0, emissions_total_mg=-1.0, throughput_vehicles=0.0)
        with self.assertRaises(ValueError):
            RawRewardMetrics(accumulated_waiting_time_seconds=0.0, queue_vehicles=0.0, stops_count=0.0, emissions_total_mg=0.0, throughput_vehicles=-1.0)

    def test_booleans_and_non_finite_rejected(self) -> None:
        with self.assertRaises(ValueError):
            RawRewardMetrics(accumulated_waiting_time_seconds=True, queue_vehicles=0.0, stops_count=0.0, emissions_total_mg=0.0, throughput_vehicles=0.0)  # type: ignore
        with self.assertRaises(ValueError):
            RawRewardMetrics(accumulated_waiting_time_seconds=float("nan"), queue_vehicles=0.0, stops_count=0.0, emissions_total_mg=0.0, throughput_vehicles=0.0)
        with self.assertRaises(ValueError):
            RawRewardMetrics(accumulated_waiting_time_seconds=float("inf"), queue_vehicles=0.0, stops_count=0.0, emissions_total_mg=0.0, throughput_vehicles=0.0)


class TestRewardScalingConfig(unittest.TestCase):
    """Test validation of RewardScalingConfig."""

    def test_valid_scales(self) -> None:
        scales = RewardScalingConfig(
            waiting_time_ref_seconds=100.0,
            queue_ref_vehicles=20.0,
            stops_ref_vehicles=10.0,
            emissions_ref_mg=500.0,
            throughput_ref_vehicles=5.0,
        )
        self.assertEqual(scales.waiting_time_ref_seconds, 100.0)

    def test_non_positive_and_non_finite_rejected(self) -> None:
        with self.assertRaises(ValueError):
            RewardScalingConfig(waiting_time_ref_seconds=0.0, queue_ref_vehicles=20.0, stops_ref_vehicles=10.0, emissions_ref_mg=500.0, throughput_ref_vehicles=5.0)
        with self.assertRaises(ValueError):
            RewardScalingConfig(waiting_time_ref_seconds=-10.0, queue_ref_vehicles=20.0, stops_ref_vehicles=10.0, emissions_ref_mg=500.0, throughput_ref_vehicles=5.0)
        with self.assertRaises(ValueError):
            RewardScalingConfig(waiting_time_ref_seconds=float("nan"), queue_ref_vehicles=20.0, stops_ref_vehicles=10.0, emissions_ref_mg=500.0, throughput_ref_vehicles=5.0)
        with self.assertRaises(ValueError):
            RewardScalingConfig(waiting_time_ref_seconds=True, queue_ref_vehicles=20.0, stops_ref_vehicles=10.0, emissions_ref_mg=500.0, throughput_ref_vehicles=5.0)  # type: ignore


class TestRewardWeights(unittest.TestCase):
    """Test validation of RewardWeights."""

    def test_valid_weights(self) -> None:
        w = RewardWeights(w_waiting_time=1.0, w_queue=0.5, w_stops=0.1, w_emissions=0.05, w_throughput=0.2)
        self.assertEqual(w.w_waiting_time, 1.0)
        self.assertEqual(w.w_queue, 0.5)

    def test_negative_and_non_finite_rejected(self) -> None:
        with self.assertRaises(ValueError):
            RewardWeights(w_waiting_time=-1.0)
        with self.assertRaises(ValueError):
            RewardWeights(w_waiting_time=float("nan"))
        with self.assertRaises(ValueError):
            RewardWeights(w_waiting_time=float("inf"))
        with self.assertRaises(ValueError):
            RewardWeights(w_waiting_time=False)  # type: ignore


class TestRewardCalculator(unittest.TestCase):
    """Test multi-objective reward calculation and component preservation."""

    def setUp(self) -> None:
        self.scales = RewardScalingConfig(
            waiting_time_ref_seconds=100.0,
            queue_ref_vehicles=20.0,
            stops_ref_vehicles=10.0,
            emissions_ref_mg=500.0,
            throughput_ref_vehicles=5.0,
        )
        self.weights = RewardWeights(
            w_waiting_time=1.0,
            w_queue=0.5,
            w_stops=0.2,
            w_emissions=0.1,
            w_throughput=0.5,
        )
        self.calculator = RewardCalculator(self.scales, self.weights)

    def test_exact_reward_calculation(self) -> None:
        """Verify mathematical correctness of scalar reward and normalized components."""
        raw = RawRewardMetrics(
            accumulated_waiting_time_seconds=50.0,  # norm = 50 / 100 = 0.5
            queue_vehicles=10.0,                   # norm = 10 / 20 = 0.5
            stops_count=2.0,                       # norm = 2 / 10 = 0.2
            emissions_total_mg=100.0,              # norm = 100 / 500 = 0.2
            throughput_vehicles=2.5,               # norm = 2.5 / 5 = 0.5
        )

        # Expected cost = 1.0*0.5 + 0.5*0.5 + 0.2*0.2 + 0.1*0.2 = 0.5 + 0.25 + 0.04 + 0.02 = 0.81
        # Expected bonus = 0.5 * 0.5 = 0.25
        # Expected scalar = -0.81 + 0.25 = -0.56
        breakdown: RewardBreakdown = self.calculator.calculate(raw)

        self.assertAlmostEqual(breakdown.normalized_waiting_time, 0.5)
        self.assertAlmostEqual(breakdown.normalized_queue, 0.5)
        self.assertAlmostEqual(breakdown.normalized_stops, 0.2)
        self.assertAlmostEqual(breakdown.normalized_emissions, 0.2)
        self.assertAlmostEqual(breakdown.normalized_throughput, 0.5)
        self.assertAlmostEqual(breakdown.scalar_reward, -0.56)

        # Crucial check: raw metrics preserved intact inside breakdown
        self.assertEqual(breakdown.raw_metrics, raw)

    def test_zero_weight_behavior_preserves_raw_metrics(self) -> None:
        """Verify that components with weight 0.0 do not affect scalar but remain in breakdown."""
        weights_zero_emissions = RewardWeights(
            w_waiting_time=1.0,
            w_queue=0.0,
            w_stops=0.0,
            w_emissions=0.0,  # zero weight
            w_throughput=0.0,
        )
        calc = RewardCalculator(self.scales, weights_zero_emissions)

        raw = RawRewardMetrics(
            accumulated_waiting_time_seconds=60.0,
            queue_vehicles=15.0,
            stops_count=5.0,
            emissions_total_mg=800.0,
            throughput_vehicles=3.0,
        )

        breakdown = calc.calculate(raw)
        # Scalar reward is purely -1.0 * (60 / 100) = -0.6
        self.assertAlmostEqual(breakdown.scalar_reward, -0.6)

        # Raw metrics and normalized values must still be recorded
        self.assertEqual(breakdown.raw_metrics.emissions_total_mg, 800.0)
        self.assertAlmostEqual(breakdown.normalized_emissions, 800.0 / 500.0)
        self.assertEqual(breakdown.raw_metrics.queue_vehicles, 15.0)
        self.assertAlmostEqual(breakdown.normalized_queue, 15.0 / 20.0)

    def test_calculator_input_validation(self) -> None:
        """Verify calculator rejects invalid inputs."""
        with self.assertRaises(ValueError):
            RewardCalculator("invalid", self.weights)  # type: ignore
        with self.assertRaises(ValueError):
            RewardCalculator(self.scales, "invalid")  # type: ignore
        with self.assertRaises(ValueError):
            self.calculator.calculate("invalid")  # type: ignore


if __name__ == "__main__":
    unittest.main()
