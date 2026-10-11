"""Unit tests for ActuatedController baseline."""

import unittest
import numpy as np

from config.schema import IntersectionConfig
from controllers.actuated import ActuatedController


class TestActuatedController(unittest.TestCase):
    """Test suite for ActuatedController initialization, validation, and control logic."""

    def setUp(self) -> None:
        """Set up standard 8-lane 2-phase test setup."""
        self.num_actions = 2
        self.num_lanes = 8
        self.action_to_lanes = {
            0: [0, 1, 2, 3],  # N-S lanes
            1: [4, 5, 6, 7],  # E-W lanes
        }
        self.controller = ActuatedController(
            num_actions=self.num_actions,
            action_to_lanes=self.action_to_lanes,
            min_green_seconds=5.0,
            max_green_seconds=45.0,
            control_interval_seconds=1.0,
            num_lanes=self.num_lanes,
            queue_threshold=0.5,
        )

        # Build dummy observation (dim: 4*8 + 2 + 2 = 36)
        # [0:8] = queues, [8:16] = counts, [16:24] = wait, [24:32] = speed, [32:34] = phase, [34] = elapsed, [35] = min_green_flag
        self.dummy_obs = np.zeros(36, dtype=np.float32)
        # Phase 0 active
        self.dummy_obs[32] = 1.0
        # Min green satisfied by default in dummy obs
        self.dummy_obs[35] = 1.0

    def test_invalid_arguments(self) -> None:
        """Test rejection of malformed or non-physical parameters."""
        with self.assertRaises(ValueError):
            ActuatedController(num_actions=0, action_to_lanes=self.action_to_lanes)

        with self.assertRaises(ValueError):
            ActuatedController(num_actions=2, action_to_lanes={})

        with self.assertRaises(ValueError):
            ActuatedController(
                num_actions=2,
                action_to_lanes=self.action_to_lanes,
                min_green_seconds=-1.0,
            )

        with self.assertRaises(ValueError):
            ActuatedController(
                num_actions=2,
                action_to_lanes=self.action_to_lanes,
                min_green_seconds=10.0,
                max_green_seconds=5.0,  # max < min
            )

        with self.assertRaises(ValueError):
            ActuatedController(
                num_actions=2,
                action_to_lanes=self.action_to_lanes,
                control_interval_seconds=0.0,
            )

        with self.assertRaises(ValueError):
            ActuatedController(
                num_actions=2,
                action_to_lanes=self.action_to_lanes,
                queue_threshold=-0.1,
            )

    def test_min_green_hold_behavior(self) -> None:
        """Controller must hold green during min-green even if approach has zero queue."""
        # Empty intersection: queue = 0, count = 0
        obs = np.zeros(36, dtype=np.float32)
        obs[35] = 0.0  # min_green not satisfied in environment yet

        # Initial action is 0
        self.assertEqual(self.controller.current_action, 0)

        # For the first 4 steps, min-green is not satisfied -> must hold action 0
        for step in range(4):
            act = self.controller.act(obs)
            self.assertEqual(act, 0)
            self.assertEqual(self.controller.current_action, 0)

    def test_gap_out_triggers_switch(self) -> None:
        """When min green is satisfied and active approach is empty, controller must gap out and switch."""
        obs = np.zeros(36, dtype=np.float32)
        obs[35] = 1.0  # min green satisfied

        # Advance 5 steps to satisfy internal min green (5.0s)
        for _ in range(4):
            self.controller.act(obs)

        # 5th step: min green is met, queue/count = 0 -> gap out!
        act = self.controller.act(obs)
        self.assertEqual(act, 1)  # Switched to Action 1
        self.assertEqual(self.controller.current_action, 1)
        self.assertEqual(self.controller.elapsed_in_phase, 0.0)

    def test_extension_when_traffic_present(self) -> None:
        """When traffic is present on active approach, controller extends green until max green."""
        obs = np.zeros(36, dtype=np.float32)
        obs[35] = 1.0  # min green satisfied
        # Put 2 vehicles on active lane 0 (North)
        obs[0] = 2.0  # queue on lane 0
        obs[8] = 2.0  # count on lane 0

        # Advance 10 steps (well past 5s min green)
        for _ in range(10):
            act = self.controller.act(obs)
            self.assertEqual(act, 0)  # Continues extending Action 0

        self.assertEqual(self.controller.current_action, 0)
        self.assertAlmostEqual(self.controller.elapsed_in_phase, 10.0)

    def test_max_green_force_off(self) -> None:
        """When max green is reached, controller forces off even if queue persists."""
        obs = np.zeros(36, dtype=np.float32)
        obs[35] = 1.0
        # Constant queue on lane 0
        obs[0] = 5.0
        obs[8] = 5.0

        # Advance until max green (45 steps at 1.0s)
        for _ in range(44):
            act = self.controller.act(obs)
            self.assertEqual(act, 0)

        # At 45th step, max green expires (45.0s) -> forced switch to Action 1
        act = self.controller.act(obs)
        self.assertEqual(act, 1)
        self.assertEqual(self.controller.current_action, 1)
        self.assertEqual(self.controller.elapsed_in_phase, 0.0)

    def test_reset(self) -> None:
        """Reset must restore initial action and zero timers."""
        obs = np.zeros(36, dtype=np.float32)
        obs[35] = 1.0
        self.controller.act(obs)
        self.controller.act(obs)
        self.assertGreater(self.controller.elapsed_in_phase, 0.0)

        self.controller.reset()
        self.assertEqual(self.controller.current_action, 0)
        self.assertEqual(self.controller.elapsed_in_phase, 0.0)

    def test_from_config_factory(self) -> None:
        """Test from_config with actual intersection configuration."""
        config = IntersectionConfig(
            tls_id="C",
            incoming_lanes=[
                "N_in_0", "N_in_1",
                "S_in_0", "S_in_1",
                "E_in_0", "E_in_1",
                "W_in_0", "W_in_1",
            ],
            green_phase_indices=[0, 2],
            min_green_seconds=5.0,
            max_green_seconds=45.0,
            control_interval_seconds=1.0,
        )
        ctrl = ActuatedController.from_config(config)
        self.assertEqual(ctrl.current_action, 0)
        self.assertEqual(ctrl.min_green_seconds, 5.0)
        self.assertEqual(ctrl.max_green_seconds, 45.0)
        # N-S lanes are indices 0..3, E-W lanes are indices 4..7
        self.assertEqual(ctrl._action_to_lanes[0], [0, 1, 2, 3])
        self.assertEqual(ctrl._action_to_lanes[1], [4, 5, 6, 7])


if __name__ == "__main__":
    unittest.main()
