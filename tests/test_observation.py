"""Unit tests for observation interface and ObservationBuilder."""

import unittest
import numpy as np

from environment.observation import (
    IntersectionMeasurement,
    LaneMeasurement,
    ObservationBuilder,
    ObservationNormalizerConfig,
)


class TestLaneMeasurement(unittest.TestCase):
    """Test validation of LaneMeasurement."""

    def test_valid_measurement(self) -> None:
        m = LaneMeasurement(
            queue_length_vehicles=5.0,
            vehicle_count=12.0,
            accumulated_waiting_time_seconds=120.5,
            average_speed_mps=8.3,
        )
        self.assertEqual(m.queue_length_vehicles, 5.0)
        self.assertEqual(m.vehicle_count, 12.0)
        self.assertEqual(m.accumulated_waiting_time_seconds, 120.5)
        self.assertEqual(m.average_speed_mps, 8.3)

    def test_negative_values_rejected(self) -> None:
        with self.assertRaises(ValueError):
            LaneMeasurement(queue_length_vehicles=-1.0, vehicle_count=5.0, accumulated_waiting_time_seconds=10.0, average_speed_mps=5.0)
        with self.assertRaises(ValueError):
            LaneMeasurement(queue_length_vehicles=1.0, vehicle_count=-5.0, accumulated_waiting_time_seconds=10.0, average_speed_mps=5.0)
        with self.assertRaises(ValueError):
            LaneMeasurement(queue_length_vehicles=1.0, vehicle_count=5.0, accumulated_waiting_time_seconds=-10.0, average_speed_mps=5.0)
        with self.assertRaises(ValueError):
            LaneMeasurement(queue_length_vehicles=1.0, vehicle_count=5.0, accumulated_waiting_time_seconds=10.0, average_speed_mps=-5.0)

    def test_booleans_and_non_finite_rejected(self) -> None:
        with self.assertRaises(ValueError):
            LaneMeasurement(queue_length_vehicles=True, vehicle_count=5.0, accumulated_waiting_time_seconds=10.0, average_speed_mps=5.0)  # type: ignore
        with self.assertRaises(ValueError):
            LaneMeasurement(queue_length_vehicles=float("nan"), vehicle_count=5.0, accumulated_waiting_time_seconds=10.0, average_speed_mps=5.0)
        with self.assertRaises(ValueError):
            LaneMeasurement(queue_length_vehicles=float("inf"), vehicle_count=5.0, accumulated_waiting_time_seconds=10.0, average_speed_mps=5.0)


class TestObservationNormalizerConfig(unittest.TestCase):
    """Test validation of ObservationNormalizerConfig."""

    def test_valid_config(self) -> None:
        cfg = ObservationNormalizerConfig(
            max_queue_per_lane=20.0,
            max_vehicles_per_lane=25.0,
            max_waiting_time_seconds=180.0,
            speed_limit_mps=13.89,
            max_green_seconds=60.0,
        )
        self.assertEqual(cfg.max_queue_per_lane, 20.0)

    def test_non_positive_and_non_finite_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ObservationNormalizerConfig(max_queue_per_lane=0.0, max_vehicles_per_lane=25.0, max_waiting_time_seconds=180.0, speed_limit_mps=13.89, max_green_seconds=60.0)
        with self.assertRaises(ValueError):
            ObservationNormalizerConfig(max_queue_per_lane=-5.0, max_vehicles_per_lane=25.0, max_waiting_time_seconds=180.0, speed_limit_mps=13.89, max_green_seconds=60.0)
        with self.assertRaises(ValueError):
            ObservationNormalizerConfig(max_queue_per_lane=float("nan"), max_vehicles_per_lane=25.0, max_waiting_time_seconds=180.0, speed_limit_mps=13.89, max_green_seconds=60.0)
        with self.assertRaises(ValueError):
            ObservationNormalizerConfig(max_queue_per_lane=True, max_vehicles_per_lane=25.0, max_waiting_time_seconds=180.0, speed_limit_mps=13.89, max_green_seconds=60.0)  # type: ignore


class TestObservationBuilder(unittest.TestCase):
    """Test deterministic observation vector construction and validation."""

    def setUp(self) -> None:
        self.lane_order = ["lane_N", "lane_S"]
        self.phase_order = [0, 2]
        self.normalizer = ObservationNormalizerConfig(
            max_queue_per_lane=10.0,
            max_vehicles_per_lane=20.0,
            max_waiting_time_seconds=100.0,
            speed_limit_mps=10.0,
            max_green_seconds=50.0,
        )

        self.lane_m_N = LaneMeasurement(
            queue_length_vehicles=5.0,
            vehicle_count=10.0,
            accumulated_waiting_time_seconds=50.0,
            average_speed_mps=5.0,
        )
        self.lane_m_S = LaneMeasurement(
            queue_length_vehicles=2.0,
            vehicle_count=8.0,
            accumulated_waiting_time_seconds=20.0,
            average_speed_mps=8.0,
        )

    def test_builder_initialization_validation(self) -> None:
        """Verify builder rejects empty or duplicate lane and phase lists."""
        with self.assertRaises(ValueError):
            ObservationBuilder(lane_order=[], green_phase_order=[0])
        with self.assertRaises(ValueError):
            ObservationBuilder(lane_order=["lane_0", "lane_0"], green_phase_order=[0])
        with self.assertRaises(ValueError):
            ObservationBuilder(lane_order=["lane_0"], green_phase_order=[])
        with self.assertRaises(ValueError):
            ObservationBuilder(lane_order=["lane_0"], green_phase_order=[0, 0])
        with self.assertRaises(ValueError):
            ObservationBuilder(lane_order=["lane_0"], green_phase_order=[True])  # type: ignore

    def test_deterministic_ordering_and_vector_shape_raw(self) -> None:
        """Verify deterministic canonical layout in raw mode."""
        builder = ObservationBuilder(self.lane_order, self.phase_order, normalizer_config=None)
        self.assertEqual(builder.vector_dim, 4 * 2 + 2 + 2)  # 12
        self.assertFalse(builder.is_normalized)

        # Deliberately construct input dictionary with reversed key order
        measurement = IntersectionMeasurement(
            lane_measurements={"lane_S": self.lane_m_S, "lane_N": self.lane_m_N},
            current_green_phase=2,
            elapsed_green_seconds=15.0,
            min_green_satisfied=True,
        )

        vec = builder.build(measurement)
        self.assertIsInstance(vec, np.ndarray)
        self.assertEqual(vec.shape, (12,))
        self.assertEqual(vec.dtype, np.float32)

        # Expected canonical layout:
        # Queues: [5.0, 2.0]
        # Counts: [10.0, 8.0]
        # Waits:  [50.0, 20.0]
        # Speeds: [5.0, 8.0]
        # OneHot: [0.0, 1.0] (phase 2 active)
        # Elapsed: 15.0
        # MinGreen: 1.0
        expected = np.array([5.0, 2.0, 10.0, 8.0, 50.0, 20.0, 5.0, 8.0, 0.0, 1.0, 15.0, 1.0], dtype=np.float32)
        np.testing.assert_allclose(vec, expected)

    def test_normalized_mode_and_clipping(self) -> None:
        """Verify values are correctly scaled and clipped to [0, 1] in normalized mode."""
        builder = ObservationBuilder(self.lane_order, self.phase_order, normalizer_config=self.normalizer)
        self.assertTrue(builder.is_normalized)

        # Normalizer scales: Q=10, C=20, W=100, S=10, G=50
        # Inputs:
        # Lane N: Q=5 (0.5), C=10 (0.5), W=50 (0.5), S=5 (0.5)
        # Lane S: Q=2 (0.2), C=8 (0.4), W=20 (0.2), S=8 (0.8)
        # Elapsed: 25.0 (0.5)
        # Phase 0 active -> OneHot: [1.0, 0.0]
        # min_green_satisfied: False -> 0.0
        measurement = IntersectionMeasurement(
            lane_measurements={"lane_N": self.lane_m_N, "lane_S": self.lane_m_S},
            current_green_phase=0,
            elapsed_green_seconds=25.0,
            min_green_satisfied=False,
        )

        vec = builder.build(measurement)
        expected = np.array([0.5, 0.2, 0.5, 0.4, 0.5, 0.2, 0.5, 0.8, 1.0, 0.0, 0.5, 0.0], dtype=np.float32)
        np.testing.assert_allclose(vec, expected)

        # Test clipping when raw values exceed scale
        overflow_lane = LaneMeasurement(
            queue_length_vehicles=20.0,  # scale is 10.0 -> clip to 1.0
            vehicle_count=40.0,         # scale is 20.0 -> clip to 1.0
            accumulated_waiting_time_seconds=200.0,  # scale is 100.0 -> clip to 1.0
            average_speed_mps=15.0,     # scale is 10.0 -> clip to 1.0
        )
        overflow_m = IntersectionMeasurement(
            lane_measurements={"lane_N": overflow_lane, "lane_S": self.lane_m_S},
            current_green_phase=0,
            elapsed_green_seconds=100.0,  # scale is 50.0 -> clip to 1.0
            min_green_satisfied=True,
        )
        vec_overflow = builder.build(overflow_m)
        self.assertTrue(np.all(vec_overflow >= 0.0))
        self.assertTrue(np.all(vec_overflow <= 1.0))
        self.assertEqual(vec_overflow[0], 1.0)  # clipped queue
        self.assertEqual(vec_overflow[2], 1.0)  # clipped count
        self.assertEqual(vec_overflow[4], 1.0)  # clipped wait
        self.assertEqual(vec_overflow[6], 1.0)  # clipped speed
        self.assertEqual(vec_overflow[10], 1.0) # clipped elapsed

    def test_missing_lane_raises_key_error(self) -> None:
        """Verify KeyError raised if a configured lane is missing from measurement."""
        builder = ObservationBuilder(self.lane_order, self.phase_order)
        incomplete_measurement = IntersectionMeasurement(
            lane_measurements={"lane_N": self.lane_m_N},  # lane_S missing
            current_green_phase=0,
            elapsed_green_seconds=10.0,
            min_green_satisfied=True,
        )
        with self.assertRaises(KeyError):
            builder.build(incomplete_measurement)

    def test_unexpected_lane_raises_value_error(self) -> None:
        """Verify ValueError raised if measurement contains extra unexpected lanes."""
        builder = ObservationBuilder(self.lane_order, self.phase_order)
        extra_lane_measurement = IntersectionMeasurement(
            lane_measurements={
                "lane_N": self.lane_m_N,
                "lane_S": self.lane_m_S,
                "lane_EXTRA": self.lane_m_S,
            },
            current_green_phase=0,
            elapsed_green_seconds=10.0,
            min_green_satisfied=True,
        )
        with self.assertRaises(ValueError):
            builder.build(extra_lane_measurement)

    def test_raw_float32_overflow_rejected(self) -> None:
        """Verify astronomical finite numbers exceeding float32 max raise ValueError in raw mode."""
        builder = ObservationBuilder(self.lane_order, self.phase_order, normalizer_config=None)
        overflow_m = IntersectionMeasurement(
            lane_measurements={
                "lane_N": LaneMeasurement(queue_length_vehicles=1e39, vehicle_count=10.0, accumulated_waiting_time_seconds=10.0, average_speed_mps=10.0),
                "lane_S": self.lane_m_S,
            },
            current_green_phase=0,
            elapsed_green_seconds=10.0,
            min_green_satisfied=True,
        )
        with self.assertRaises(ValueError):
            builder.build(overflow_m)


if __name__ == "__main__":
    unittest.main()
