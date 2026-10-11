"""Unit and integration tests for SumoGymAdapter."""

import math
import os
import unittest
import numpy as np

from gymnasium import spaces
from gymnasium.utils.env_checker import check_env

from config.schema import IntersectionConfig
from environment.gym_wrapper import SumoGymAdapter
from environment.observation import ObservationBuilder, ObservationNormalizerConfig
from environment.reward import RewardCalculator, RewardScalingConfig, RewardWeights
from environment.sumo_environment import SumoEnvironment
from tests.test_evaluation_runner import MockTraciModule


class TestSumoGymAdapterUnit(unittest.TestCase):
    """Unit tests for SumoGymAdapter using Mock TraCI."""

    def setUp(self) -> None:
        self.config = IntersectionConfig(
            tls_id="J1",
            incoming_lanes=["lane_0", "lane_1"],
            green_phase_indices=[0, 2],
            min_green_seconds=5.0,
            max_green_seconds=50.0,
            control_interval_seconds=1.0,
            exit_lanes=["exit_0"],
        )
        self.mock_traci = MockTraciModule(max_steps=5, lane_ids=["lane_0", "lane_1", "exit_0"])

    def test_invalid_constructor_argument(self) -> None:
        """Reject non-SumoEnvironment instances in constructor."""
        with self.assertRaises(ValueError):
            SumoGymAdapter("invalid_env")  # type: ignore

    def test_raw_spaces_and_properties(self) -> None:
        """Verify spaces and properties in raw observation mode."""
        env = SumoEnvironment(
            self.config,
            net_file="dummy.net.xml",
            route_file="dummy.rou.xml",
            traci_module=self.mock_traci,
        )
        adapter = SumoGymAdapter(env)

        self.assertFalse(adapter.is_normalized)
        self.assertIsInstance(adapter.action_space, spaces.Discrete)
        self.assertEqual(adapter.action_space.n, 2)

        # 4*2 + 2 + 2 = 12
        self.assertIsInstance(adapter.observation_space, spaces.Box)
        self.assertEqual(adapter.observation_space.shape, (12,))
        self.assertEqual(adapter.observation_space.dtype, np.float32)

        adapter.close()

    def test_normalized_spaces(self) -> None:
        """Verify spaces in normalized observation mode."""
        norm_cfg = ObservationNormalizerConfig(
            max_queue_per_lane=10.0,
            max_vehicles_per_lane=20.0,
            max_waiting_time_seconds=100.0,
            speed_limit_mps=13.89,
            max_green_seconds=50.0,
        )
        builder = ObservationBuilder(
            lane_order=self.config.incoming_lanes,
            green_phase_order=self.config.green_phase_indices,
            normalizer_config=norm_cfg,
        )
        env = SumoEnvironment(
            self.config,
            net_file="dummy.net.xml",
            route_file="dummy.rou.xml",
            observation_builder=builder,
            traci_module=self.mock_traci,
        )
        adapter = SumoGymAdapter(env)

        self.assertTrue(adapter.is_normalized)
        self.assertTrue(np.all(adapter.observation_space.low == 0.0))
        self.assertTrue(np.all(adapter.observation_space.high == 1.0))

        adapter.close()

    def test_step_before_reset_raises_runtime_error(self) -> None:
        """Verify step raises RuntimeError if called before reset."""
        env = SumoEnvironment(
            self.config,
            net_file="dummy.net.xml",
            route_file="dummy.rou.xml",
            traci_module=self.mock_traci,
        )
        adapter = SumoGymAdapter(env)

        with self.assertRaises(RuntimeError):
            adapter.step(0)

        adapter.close()

    def test_invalid_action_rejected(self) -> None:
        """Verify out-of-bounds actions raise ValueError."""
        env = SumoEnvironment(
            self.config,
            net_file="dummy.net.xml",
            route_file="dummy.rou.xml",
            traci_module=self.mock_traci,
        )
        adapter = SumoGymAdapter(env)
        adapter.reset()

        with self.assertRaises(ValueError):
            adapter.step(99)

        with self.assertRaises(ValueError):
            adapter.step(-1)

        adapter.close()

    def test_reset_and_step_signatures_with_mock(self) -> None:
        """Verify Gymnasium-compliant return signatures on reset and step."""
        env = SumoEnvironment(
            self.config,
            net_file="dummy.net.xml",
            route_file="dummy.rou.xml",
            traci_module=self.mock_traci,
        )
        adapter = SumoGymAdapter(env)

        obs, info = adapter.reset(seed=42)
        self.assertIsInstance(obs, np.ndarray)
        self.assertEqual(obs.dtype, np.float32)
        self.assertIsInstance(info, dict)
        self.assertTrue(adapter.observation_space.contains(obs))

        next_obs, reward, term, trunc, info = adapter.step(0)
        self.assertIsInstance(next_obs, np.ndarray)
        self.assertIsInstance(reward, float)
        self.assertIsInstance(term, bool)
        self.assertIsInstance(trunc, bool)
        self.assertIsInstance(info, dict)

        adapter.close()
        self.assertTrue(adapter._is_closed)


class TestSumoGymAdapterRealSumo(unittest.TestCase):
    """Integration test suite executing SumoGymAdapter on real SUMO research intersection."""

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

        norm_cfg = ObservationNormalizerConfig(
            max_queue_per_lane=20.0,
            max_vehicles_per_lane=25.0,
            max_waiting_time_seconds=100.0,
            speed_limit_mps=13.89,
            max_green_seconds=45.0,
        )
        self.obs_builder = ObservationBuilder(
            lane_order=self.config.incoming_lanes,
            green_phase_order=self.config.green_phase_indices,
            normalizer_config=norm_cfg,
        )

        scales = RewardScalingConfig(100.0, 10.0, 5.0, 100000.0, 10.0)
        weights = RewardWeights(1.0, 0.5, 0.1, 0.1, 0.5)
        self.reward_calc = RewardCalculator(scales, weights)

        self.gym_env = None

    def tearDown(self) -> None:
        if self.gym_env is not None:
            self.gym_env.close()

    def test_gymnasium_env_checker_passes(self) -> None:
        """Run gymnasium.utils.env_checker.check_env() on real SUMO environment."""
        sumo_env = SumoEnvironment(
            self.config,
            self.net_file,
            self.route_file,
            observation_builder=self.obs_builder,
            reward_calculator=self.reward_calc,
            max_steps=50,
        )
        self.gym_env = SumoGymAdapter(sumo_env)

        # check_env performs extensive validation on reset, step, spaces, and dtypes
        check_env(self.gym_env)

    def test_seeded_reset_reproducibility(self) -> None:
        """Verify identical observations across identical seeded resets."""
        sumo_env1 = SumoEnvironment(
            self.config,
            self.net_file,
            self.route_file,
            observation_builder=self.obs_builder,
            reward_calculator=self.reward_calc,
        )
        adapter1 = SumoGymAdapter(sumo_env1)
        obs1, _ = adapter1.reset(seed=123)
        adapter1.close()

        sumo_env2 = SumoEnvironment(
            self.config,
            self.net_file,
            self.route_file,
            observation_builder=self.obs_builder,
            reward_calculator=self.reward_calc,
        )
        adapter2 = SumoGymAdapter(sumo_env2)
        obs2, _ = adapter2.reset(seed=123)
        adapter2.close()

        np.testing.assert_allclose(obs1, obs2, rtol=1e-5, atol=1e-5)

    def test_random_action_short_episode(self) -> None:
        """Execute random actions through the adapter until natural termination."""
        sumo_env = SumoEnvironment(
            self.config,
            self.net_file,
            self.route_file,
            observation_builder=self.obs_builder,
            reward_calculator=self.reward_calc,
            max_steps=100,
        )
        self.gym_env = SumoGymAdapter(sumo_env)

        obs, info = self.gym_env.reset(seed=42)
        self.assertEqual(obs.shape, (36,))
        self.assertTrue(self.gym_env.observation_space.contains(obs))

        terminated = False
        truncated = False
        step_count = 0

        rng = np.random.RandomState(42)
        while not (terminated or truncated):
            action = int(rng.choice([0, 1]))
            next_obs, reward, terminated, truncated, info = self.gym_env.step(action)

            self.assertTrue(self.gym_env.observation_space.contains(next_obs))
            self.assertTrue(math.isfinite(reward))
            self.assertIsInstance(terminated, bool)
            self.assertIsInstance(truncated, bool)
            step_count += 1

        self.assertTrue(terminated or truncated)
        self.assertGreater(step_count, 0)


if __name__ == "__main__":
    unittest.main()
