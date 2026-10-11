"""Integration tests for the real research intersection.

This module validates that SumoEnvironment correctly interfaces with the actual
research intersection files (environment/single_intersection.net.xml,
environment/routes.rou.xml, and TLS ID C), enforcing signal clearance safety,
topology validation, deterministic observation layouts, and throughput tracking.
"""

import os
import unittest
import numpy as np

from config.schema import IntersectionConfig
from environment.sumo_environment import SumoEnvironment


class TestActualIntersectionIntegration(unittest.TestCase):
    """Integration test suite executing real SUMO on the research intersection."""

    def setUp(self) -> None:
        self.net_file = os.path.abspath("environment/single_intersection.net.xml")
        self.route_file = os.path.abspath("environment/routes.rou.xml")
        self.config = IntersectionConfig(
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
            yellow_seconds=3.0,
            all_red_seconds=0.0,
            clearance_handled_by_sumo=True,
            exit_lanes=[
                "N_out_0", "N_out_1",
                "S_out_0", "S_out_1",
                "E_out_0", "E_out_1",
                "W_out_0", "W_out_1",
            ],
        )
        self.env = None

    def tearDown(self) -> None:
        if self.env is not None:
            self.env.close()

    def test_actual_intersection_lifecycle_and_topology(self) -> None:
        """Verify real SUMO launches on actual intersection and produces 36-dim observation."""
        self.env = SumoEnvironment(
            config=self.config,
            net_file=self.net_file,
            route_file=self.route_file,
        )
        obs, info = self.env.reset(seed=42)

        self.assertTrue(self.env.is_running)
        self.assertEqual(info["step"], 0)
        self.assertEqual(info["active_green_phase"], 0)
        self.assertFalse(info["min_green_satisfied"])
        self.assertTrue(info["throughput_tracking_active"])

        # Layout: 4 features * 8 lanes + 2 phases + 2 flags = 36
        self.assertEqual(obs.shape, (36,))
        self.assertEqual(obs.dtype, np.float32)
        self.assertTrue(np.all(np.isfinite(obs)))

    def test_actual_intersection_clearance_extraction(self) -> None:
        """Verify automatic extraction of genuine clearance phases from tlLogic C."""
        self.env = SumoEnvironment(
            config=self.config,
            net_file=self.net_file,
            route_file=self.route_file,
        )
        self.env.reset(seed=42)

        sequences = self.env.clearance_sequences
        self.assertIn((0, 2), sequences)
        self.assertIn((2, 0), sequences)

        # Transition 0 -> 2 must use Phase 1 (Yellow N-S) for 3.0s
        self.assertEqual(len(sequences[(0, 2)]), 1)
        self.assertEqual(sequences[(0, 2)][0].phase_index, 1)
        self.assertEqual(sequences[(0, 2)][0].duration_seconds, 3.0)

        # Transition 2 -> 0 must use Phase 3 (Yellow E-W) for 3.0s
        self.assertEqual(len(sequences[(2, 0)]), 1)
        self.assertEqual(sequences[(2, 0)][0].phase_index, 3)
        self.assertEqual(sequences[(2, 0)][0].duration_seconds, 3.0)

    def test_actual_intersection_safety_and_bidirectional_clearance(self) -> None:
        """Verify safety enforcement and active yellow clearance execution in both directions."""
        self.env = SumoEnvironment(
            config=self.config,
            net_file=self.net_file,
            route_file=self.route_file,
        )
        self.env.reset(seed=42)

        # 1. Min-green enforcement: Request Phase 2 at t=0 must be rejected
        obs, r, term, trunc, info = self.env.step(action=1)
        self.assertFalse(info["action_accepted"])
        self.assertIn("Minimum green not satisfied", info["action_reason"])
        self.assertEqual(info["active_green_phase"], 0)
        self.assertFalse(info["clearance_executed"])

        # 2. Hold Phase 0 for 4 more steps to satisfy 5.0s min-green
        for _ in range(4):
            obs, r, term, trunc, info = self.env.step(action=0)
            self.assertTrue(info["action_accepted"])

        self.assertTrue(info["min_green_satisfied"])
        self.assertEqual(info["active_green_phase"], 0)

        # 3. Transition 0 -> 2: Must execute Phase 1 (Yellow) for 3.0s
        obs, r, term, trunc, info = self.env.step(action=1)
        self.assertTrue(info["action_accepted"])
        self.assertTrue(info["clearance_executed"])
        self.assertEqual(info["clearance_phases"], [1])
        self.assertAlmostEqual(info["clearance_duration_seconds"], 3.0, places=2)
        self.assertEqual(info["active_green_phase"], 2)
        # Time: 5s green + 3s yellow + 1s green = 9.0s
        self.assertEqual(info["simulation_time"], 9.0)

        # 4. Hold Phase 2 for 4 steps to satisfy min-green (5.0s total in Phase 2)
        for _ in range(4):
            obs, r, term, trunc, info = self.env.step(action=1)
            self.assertTrue(info["action_accepted"])

        self.assertTrue(info["min_green_satisfied"])

        # 5. Reverse transition 2 -> 0: Must execute Phase 3 (Yellow) for 3.0s
        obs, r, term, trunc, info = self.env.step(action=0)
        self.assertTrue(info["action_accepted"])
        self.assertTrue(info["clearance_executed"])
        self.assertEqual(info["clearance_phases"], [3])
        self.assertAlmostEqual(info["clearance_duration_seconds"], 3.0, places=2)
        self.assertEqual(info["active_green_phase"], 0)
        # Time: 9s + 4s green + 3s yellow + 1s green = 17.0s
        self.assertEqual(info["simulation_time"], 17.0)

    def test_actual_intersection_full_episode_and_throughput(self) -> None:
        """Verify full episode simulation to natural termination with exact throughput count."""
        self.env = SumoEnvironment(
            config=self.config,
            net_file=self.net_file,
            route_file=self.route_file,
            max_steps=200,
        )
        self.env.reset(seed=101)

        total_throughput = 0.0
        steps = 0
        terminated = False
        truncated = False

        while not (terminated or truncated):
            # Alternate green phases periodically after min-green
            action = 0 if (steps // 10) % 2 == 0 else 1
            obs, r, terminated, truncated, info = self.env.step(action)
            total_throughput += info["raw_metrics"].throughput_vehicles
            steps += 1

        # All 8 vehicles from routes.rou.xml must complete their crossing
        self.assertEqual(total_throughput, 8.0)
        self.assertTrue(terminated)
        self.assertFalse(truncated)
        self.assertEqual(info["expected_vehicles"], 0)


if __name__ == "__main__":
    unittest.main()
