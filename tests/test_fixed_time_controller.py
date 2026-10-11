"""Unit tests for the FixedTimeController baseline."""

import unittest
import numpy as np

from config.schema import IntersectionConfig
from controllers.fixed_time import FixedTimeController


class TestFixedTimeController(unittest.TestCase):
    """Test suite for FixedTimeController initialization, validation, and execution."""

    def setUp(self) -> None:
        """Set up dummy valid observation and default controller."""
        self.dummy_obs = np.zeros(20, dtype=np.float32)
        self.durations = {0: 30.0, 1: 20.0}
        self.controller = FixedTimeController(
            phase_durations=self.durations,
            control_interval_seconds=1.0,
            phase_sequence=[0, 1],
        )

    def test_invalid_phase_durations(self) -> None:
        """Test rejection of malformed phase duration mappings."""
        with self.assertRaises(ValueError):
            FixedTimeController(phase_durations={})

        with self.assertRaises(ValueError):
            FixedTimeController(phase_durations="invalid")  # type: ignore

        with self.assertRaises(ValueError):
            FixedTimeController(phase_durations={-1: 30.0})

        with self.assertRaises(ValueError):
            FixedTimeController(phase_durations={True: 30.0})  # type: ignore

        with self.assertRaises(ValueError):
            FixedTimeController(phase_durations={0: -5.0})

        with self.assertRaises(ValueError):
            FixedTimeController(phase_durations={0: 0.0})

        with self.assertRaises(ValueError):
            FixedTimeController(phase_durations={0: float("nan")})

        with self.assertRaises(ValueError):
            FixedTimeController(phase_durations={0: float("inf")})

        with self.assertRaises(ValueError):
            FixedTimeController(phase_durations={0: True})  # type: ignore

    def test_invalid_control_interval(self) -> None:
        """Test rejection of non-positive or non-finite control intervals."""
        with self.assertRaises(ValueError):
            FixedTimeController(self.durations, control_interval_seconds=0.0)

        with self.assertRaises(ValueError):
            FixedTimeController(self.durations, control_interval_seconds=-1.0)

        with self.assertRaises(ValueError):
            FixedTimeController(self.durations, control_interval_seconds=float("inf"))

        with self.assertRaises(ValueError):
            FixedTimeController(self.durations, control_interval_seconds=True)  # type: ignore

    def test_invalid_phase_sequence(self) -> None:
        """Test rejection of malformed phase sequences."""
        with self.assertRaises(ValueError):
            FixedTimeController(self.durations, phase_sequence=[])

        with self.assertRaises(ValueError):
            FixedTimeController(self.durations, phase_sequence="invalid")  # type: ignore

        with self.assertRaises(ValueError):
            FixedTimeController(self.durations, phase_sequence=[0, 2])  # 2 not in durations

    def test_default_sequence_and_properties(self) -> None:
        """Test default sorted sequence construction and accessors."""
        ctrl = FixedTimeController({2: 15.0, 0: 25.0})
        self.assertEqual(ctrl.phase_sequence, [0, 2])
        self.assertEqual(ctrl.current_action, 0)
        self.assertEqual(ctrl.elapsed_in_phase, 0.0)
        self.assertEqual(ctrl.phase_durations, {0: 25.0, 2: 15.0})
        self.assertEqual(ctrl.control_interval_seconds, 1.0)

    def test_deterministic_cycling(self) -> None:
        """Test exact step progression and sequence wrap-around."""
        # 2 actions: action 0 for 3.0s, action 1 for 2.0s, interval 1.0s
        ctrl = FixedTimeController(
            phase_durations={0: 3.0, 1: 2.0},
            control_interval_seconds=1.0,
            phase_sequence=[0, 1],
        )

        # Action 0: 3 steps
        a1 = ctrl.act(self.dummy_obs)
        self.assertEqual(a1, 0)
        self.assertAlmostEqual(ctrl.elapsed_in_phase, 1.0)

        a2 = ctrl.act(self.dummy_obs)
        self.assertEqual(a2, 0)
        self.assertAlmostEqual(ctrl.elapsed_in_phase, 2.0)

        a3 = ctrl.act(self.dummy_obs)
        self.assertEqual(a3, 0)
        # Action completed: pointer shifted to next action, timer reset
        self.assertAlmostEqual(ctrl.elapsed_in_phase, 0.0)
        self.assertEqual(ctrl.current_action, 1)

        # Action 1: 2 steps
        a4 = ctrl.act(self.dummy_obs)
        self.assertEqual(a4, 1)
        self.assertAlmostEqual(ctrl.elapsed_in_phase, 1.0)

        a5 = ctrl.act(self.dummy_obs)
        self.assertEqual(a5, 1)
        self.assertAlmostEqual(ctrl.elapsed_in_phase, 0.0)
        self.assertEqual(ctrl.current_action, 0)

        # Back to Action 0
        a6 = ctrl.act(self.dummy_obs)
        self.assertEqual(a6, 0)
        self.assertAlmostEqual(ctrl.elapsed_in_phase, 1.0)

    def test_act_observation_validation(self) -> None:
        """Test strict validation of input observations."""
        with self.assertRaises(ValueError):
            self.controller.act([0.0, 1.0])  # type: ignore (not ndarray)

        with self.assertRaises(ValueError):
            self.controller.act(np.zeros((2, 2), dtype=np.float32))  # 2D array

        with self.assertRaises(ValueError):
            self.controller.act(np.array([0.0, np.nan], dtype=np.float32))

        with self.assertRaises(ValueError):
            self.controller.act(np.array([0.0, np.inf], dtype=np.float32))

    def test_reset(self) -> None:
        """Test reset restores sequence pointer and elapsed timer."""
        # Advance 2 steps into phase 0
        self.controller.act(self.dummy_obs)
        self.controller.act(self.dummy_obs)
        self.assertAlmostEqual(self.controller.elapsed_in_phase, 2.0)

        self.controller.reset()
        self.assertEqual(self.controller.current_action, 0)
        self.assertEqual(self.controller.elapsed_in_phase, 0.0)

    def test_from_config(self) -> None:
        """Test instantiation via from_config factory."""
        config = IntersectionConfig(
            tls_id="tls_test",
            incoming_lanes=["L1", "L2"],
            green_phase_indices=[0, 2],
            min_green_seconds=5.0,
            max_green_seconds=60.0,
            control_interval_seconds=2.0,
        )

        ctrl = FixedTimeController.from_config(config, default_green_seconds=42.0)
        self.assertEqual(ctrl.control_interval_seconds, 2.0)
        self.assertEqual(ctrl.phase_durations, {0: 42.0, 1: 42.0})
        self.assertEqual(ctrl.phase_sequence, [0, 1])

        # Test duration override
        ctrl_override = FixedTimeController.from_config(
            config,
            phase_durations_override={0: 25.0, 1: 35.0},
        )
        self.assertEqual(ctrl_override.phase_durations, {0: 25.0, 1: 35.0})


if __name__ == "__main__":
    unittest.main()
