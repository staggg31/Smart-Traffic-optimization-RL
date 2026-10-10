"""Unit tests for intersection configuration schema and base controller interface."""

import unittest
import numpy as np

from config.schema import IntersectionConfig
from controllers.base import BaseTrafficController


class TestIntersectionConfig(unittest.TestCase):
    """Test suite for IntersectionConfig validation."""

    def test_valid_configuration(self) -> None:
        """Verify successful instantiation with valid parameters."""
        config = IntersectionConfig(
            tls_id="J1",
            incoming_lanes=["lane_N_0", "lane_S_0", "lane_E_0", "lane_W_0"],
            green_phase_indices=[0, 2],
            min_green_seconds=10.0,
            max_green_seconds=45.0,
            control_interval_seconds=1.0,
            yellow_seconds=3.0,
            all_red_seconds=1.0,
            clearance_handled_by_sumo=False,
        )
        self.assertEqual(config.tls_id, "J1")
        self.assertEqual(len(config.incoming_lanes), 4)
        self.assertEqual(config.green_phase_indices, [0, 2])
        self.assertEqual(config.min_green_seconds, 10.0)
        self.assertEqual(config.max_green_seconds, 45.0)
        self.assertEqual(config.control_interval_seconds, 1.0)
        self.assertEqual(config.yellow_seconds, 3.0)
        self.assertEqual(config.all_red_seconds, 1.0)
        self.assertFalse(config.clearance_handled_by_sumo)

    def test_missing_or_blank_tls_id(self) -> None:
        """Verify missing or whitespace-only TLS identifier raises ValueError."""
        with self.assertRaises(ValueError):
            IntersectionConfig(
                tls_id="",
                incoming_lanes=["lane_0"],
                green_phase_indices=[0],
                min_green_seconds=10.0,
                max_green_seconds=30.0,
            )

        with self.assertRaises(ValueError):
            IntersectionConfig(
                tls_id="   ",
                incoming_lanes=["lane_0"],
                green_phase_indices=[0],
                min_green_seconds=10.0,
                max_green_seconds=30.0,
            )

    def test_empty_or_invalid_incoming_lanes(self) -> None:
        """Verify empty, malformed, or duplicate incoming lane lists raise ValueError."""
        # Empty list
        with self.assertRaises(ValueError):
            IntersectionConfig(
                tls_id="J1",
                incoming_lanes=[],
                green_phase_indices=[0],
                min_green_seconds=10.0,
                max_green_seconds=30.0,
            )

        # Blank lane ID string
        with self.assertRaises(ValueError):
            IntersectionConfig(
                tls_id="J1",
                incoming_lanes=["lane_0", ""],
                green_phase_indices=[0],
                min_green_seconds=10.0,
                max_green_seconds=30.0,
            )

        # Duplicate lane IDs
        with self.assertRaises(ValueError):
            IntersectionConfig(
                tls_id="J1",
                incoming_lanes=["lane_0", "lane_0"],
                green_phase_indices=[0],
                min_green_seconds=10.0,
                max_green_seconds=30.0,
            )

    def test_empty_or_invalid_green_phase_indices(self) -> None:
        """Verify empty, negative, or duplicate green phase indices raise ValueError."""
        # Empty list
        with self.assertRaises(ValueError):
            IntersectionConfig(
                tls_id="J1",
                incoming_lanes=["lane_0"],
                green_phase_indices=[],
                min_green_seconds=10.0,
                max_green_seconds=30.0,
            )

        # Negative index
        with self.assertRaises(ValueError):
            IntersectionConfig(
                tls_id="J1",
                incoming_lanes=["lane_0"],
                green_phase_indices=[-1],
                min_green_seconds=10.0,
                max_green_seconds=30.0,
            )

        # Duplicate phase indices
        with self.assertRaises(ValueError):
            IntersectionConfig(
                tls_id="J1",
                incoming_lanes=["lane_0"],
                green_phase_indices=[0, 0],
                min_green_seconds=10.0,
                max_green_seconds=30.0,
            )

    def test_invalid_min_green_timings(self) -> None:
        """Verify non-positive min_green_seconds raises ValueError."""
        with self.assertRaises(ValueError):
            IntersectionConfig(
                tls_id="J1",
                incoming_lanes=["lane_0"],
                green_phase_indices=[0],
                min_green_seconds=0.0,
                max_green_seconds=30.0,
            )

        with self.assertRaises(ValueError):
            IntersectionConfig(
                tls_id="J1",
                incoming_lanes=["lane_0"],
                green_phase_indices=[0],
                min_green_seconds=-5.0,
                max_green_seconds=30.0,
            )

    def test_invalid_max_green_timings(self) -> None:
        """Verify zero or negative max_green_seconds raises ValueError."""
        with self.assertRaises(ValueError):
            IntersectionConfig(
                tls_id="J1",
                incoming_lanes=["lane_0"],
                green_phase_indices=[0],
                min_green_seconds=10.0,
                max_green_seconds=0.0,
            )

        with self.assertRaises(ValueError):
            IntersectionConfig(
                tls_id="J1",
                incoming_lanes=["lane_0"],
                green_phase_indices=[0],
                min_green_seconds=10.0,
                max_green_seconds=-10.0,
            )

    def test_min_green_exceeds_max_green(self) -> None:
        """Verify min_green_seconds > max_green_seconds raises ValueError."""
        with self.assertRaises(ValueError):
            IntersectionConfig(
                tls_id="J1",
                incoming_lanes=["lane_0"],
                green_phase_indices=[0],
                min_green_seconds=35.0,
                max_green_seconds=20.0,
            )

    def test_invalid_control_interval(self) -> None:
        """Verify non-positive control_interval_seconds raises ValueError."""
        with self.assertRaises(ValueError):
            IntersectionConfig(
                tls_id="J1",
                incoming_lanes=["lane_0"],
                green_phase_indices=[0],
                min_green_seconds=10.0,
                max_green_seconds=30.0,
                control_interval_seconds=0.0,
            )

        with self.assertRaises(ValueError):
            IntersectionConfig(
                tls_id="J1",
                incoming_lanes=["lane_0"],
                green_phase_indices=[0],
                min_green_seconds=10.0,
                max_green_seconds=30.0,
                control_interval_seconds=-1.0,
            )

    def test_negative_clearance_timings(self) -> None:
        """Verify negative yellow or all-red durations raise ValueError."""
        with self.assertRaises(ValueError):
            IntersectionConfig(
                tls_id="J1",
                incoming_lanes=["lane_0"],
                green_phase_indices=[0],
                min_green_seconds=10.0,
                max_green_seconds=30.0,
                yellow_seconds=-1.0,
            )

        with self.assertRaises(ValueError):
            IntersectionConfig(
                tls_id="J1",
                incoming_lanes=["lane_0"],
                green_phase_indices=[0],
                min_green_seconds=10.0,
                max_green_seconds=30.0,
                all_red_seconds=-0.5,
            )

    def test_non_finite_timing_fields_rejected(self) -> None:
        """Verify NaN, +inf, and -inf are rejected for every timing field."""
        timing_fields = [
            "min_green_seconds",
            "max_green_seconds",
            "control_interval_seconds",
            "yellow_seconds",
            "all_red_seconds",
        ]
        non_finite_values = [float("nan"), float("inf"), float("-inf")]

        for field_name in timing_fields:
            for bad_val in non_finite_values:
                kwargs = {
                    "tls_id": "J1",
                    "incoming_lanes": ["lane_0"],
                    "green_phase_indices": [0],
                    "min_green_seconds": 10.0,
                    "max_green_seconds": 30.0,
                    "control_interval_seconds": 1.0,
                    "yellow_seconds": 3.0,
                    "all_red_seconds": 1.0,
                }
                kwargs[field_name] = bad_val
                with self.assertRaises(ValueError, msg=f"{field_name} accepted {bad_val}"):
                    IntersectionConfig(**kwargs)

    def test_booleans_and_inappropriate_types_rejected_for_timing_fields(self) -> None:
        """Verify booleans and non-numeric types are rejected for every timing field."""
        timing_fields = [
            "min_green_seconds",
            "max_green_seconds",
            "control_interval_seconds",
            "yellow_seconds",
            "all_red_seconds",
        ]
        inappropriate_values = [True, False, "10.0", None]

        for field_name in timing_fields:
            for bad_val in inappropriate_values:
                kwargs = {
                    "tls_id": "J1",
                    "incoming_lanes": ["lane_0"],
                    "green_phase_indices": [0],
                    "min_green_seconds": 10.0,
                    "max_green_seconds": 30.0,
                    "control_interval_seconds": 1.0,
                    "yellow_seconds": 3.0,
                    "all_red_seconds": 1.0,
                }
                kwargs[field_name] = bad_val
                with self.assertRaises(ValueError, msg=f"{field_name} accepted {bad_val}"):
                    IntersectionConfig(**kwargs)

    def test_boolean_in_green_phase_indices_rejected(self) -> None:
        """Verify booleans inside green_phase_indices are rejected despite being int subclass."""
        with self.assertRaises(ValueError):
            IntersectionConfig(
                tls_id="J1",
                incoming_lanes=["lane_0"],
                green_phase_indices=[True],
                min_green_seconds=10.0,
                max_green_seconds=30.0,
            )

        with self.assertRaises(ValueError):
            IntersectionConfig(
                tls_id="J1",
                incoming_lanes=["lane_0"],
                green_phase_indices=[0, False],
                min_green_seconds=10.0,
                max_green_seconds=30.0,
            )

    def test_invalid_clearance_handled_by_sumo_type(self) -> None:
        """Verify non-boolean clearance_handled_by_sumo raises ValueError."""
        with self.assertRaises(ValueError):
            IntersectionConfig(
                tls_id="J1",
                incoming_lanes=["lane_0"],
                green_phase_indices=[0],
                min_green_seconds=10.0,
                max_green_seconds=30.0,
                clearance_handled_by_sumo="True",  # type: ignore
            )


class TestBaseTrafficController(unittest.TestCase):
    """Test suite for BaseTrafficController abstraction."""

    def test_cannot_instantiate_abstract_controller(self) -> None:
        """Verify BaseTrafficController cannot be instantiated directly."""
        with self.assertRaises(TypeError):
            BaseTrafficController()  # type: ignore

    def test_concrete_controller_implementation(self) -> None:
        """Verify concrete subclass can implement abstract interface."""
        class DummyController(BaseTrafficController):
            def __init__(self) -> None:
                self.reset_called = False

            def act(self, observation: np.ndarray) -> int:
                return 0

            def reset(self) -> None:
                self.reset_called = True

        controller = DummyController()
        action = controller.act(np.zeros(5))
        self.assertEqual(action, 0)
        controller.reset()
        self.assertTrue(controller.reset_called)


if __name__ == "__main__":
    unittest.main()
