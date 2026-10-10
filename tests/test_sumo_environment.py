"""Unit and integration tests for SumoEnvironment wrapper."""

import os
import unittest
from unittest.mock import MagicMock
import numpy as np

from config.schema import IntersectionConfig
from environment.observation import ObservationBuilder
from environment.reward import RewardCalculator, RewardScalingConfig, RewardWeights
from environment.sumo_environment import SumoEnvironment


class MockTrafficLight:
    def __init__(self, tls_ids=None):
        self._tls_ids = tls_ids if tls_ids is not None else ["J1"]
        self.current_phase = 0
        self.set_phase_calls = []

    def getIDList(self):
        return list(self._tls_ids)

    def setPhase(self, tls_id, phase_index):
        self.current_phase = phase_index
        self.set_phase_calls.append((tls_id, phase_index))

    def getAllProgramLogics(self, tls_id):
        return []


class MockLane:
    def __init__(self, lane_ids=None):
        self._lane_ids = lane_ids if lane_ids is not None else ["lane_0", "lane_1", "exit_0"]

    def getIDList(self):
        return list(self._lane_ids)

    def getLastStepHaltingNumber(self, lane_id):
        return 3

    def getLastStepVehicleNumber(self, lane_id):
        return 5

    def getWaitingTime(self, lane_id):
        return 45.0

    def getLastStepMeanSpeed(self, lane_id):
        return 7.5

    def getCO2Emission(self, lane_id):
        return 120.0

    def getLastStepVehicleIDs(self, lane_id):
        if lane_id == "exit_0":
            return ["veh_1"]  # veh_1 was on incoming, now on exit
        return ["veh_1", "veh_2"]


class MockSimulation:
    def __init__(self):
        self.time = 0.0

    def getTime(self):
        return self.time

    def getMinExpectedNumber(self):
        return 10


class MockVehicle:
    def getSpeed(self, veh_id):
        return 0.05  # halted (< 0.1 m/s)


class MockTraciModule:
    """Mock TraCI module for lifecycle and interaction testing."""

    def __init__(self, available_tls=None, available_lanes=None):
        self.trafficlight = MockTrafficLight(available_tls)
        self.lane = MockLane(available_lanes)
        self.simulation = MockSimulation()
        self.vehicle = MockVehicle()
        self.is_started = False
        self.step_calls = 0
        self.start_calls = []

    def start(self, cmd):
        self.is_started = True
        self.start_calls.append(cmd)

    def simulationStep(self):
        self.step_calls += 1
        self.simulation.time += 1.0

    def close(self):
        self.is_started = False


class TestSumoEnvironmentWithMock(unittest.TestCase):
    """Test suite using MockTraci for deterministic lifecycle and safety verification."""

    def setUp(self) -> None:
        self.config = IntersectionConfig(
            tls_id="J1",
            incoming_lanes=["lane_0", "lane_1"],
            green_phase_indices=[0, 2],
            min_green_seconds=10.0,
            max_green_seconds=30.0,
            control_interval_seconds=1.0,
            clearance_handled_by_sumo=True,
        )
        self.mock_traci = MockTraciModule()
        self.scales = RewardScalingConfig(
            waiting_time_ref_seconds=100.0,
            queue_ref_vehicles=20.0,
            stops_ref_vehicles=10.0,
            emissions_ref_mg=500.0,
            throughput_ref_vehicles=5.0,
        )
        self.weights = RewardWeights()
        self.reward_calc = RewardCalculator(self.scales, self.weights)
        self.obs_builder = ObservationBuilder(
            lane_order=["lane_0", "lane_1"],
            green_phase_order=[0, 2],
            normalizer_config=None,
        )

    def test_reset_and_initial_observation(self) -> None:
        """Verify reset initializes TraCI, validates network, and returns observation."""
        env = SumoEnvironment(
            config=self.config,
            net_file="dummy.net.xml",
            route_file="dummy.rou.xml",
            traci_module=self.mock_traci,
            observation_builder=self.obs_builder,
            reward_calculator=self.reward_calc,
            exit_lanes=["exit_0"],
            sumo_binary="sumo",
        )

        obs, info = env.reset(seed=42)
        self.assertTrue(env.is_running)
        self.assertEqual(len(self.mock_traci.start_calls), 1)
        self.assertIn("--seed", self.mock_traci.start_calls[0])
        self.assertIn("42", self.mock_traci.start_calls[0])

        # Vector dimension: 4 * 2 (lanes) + 2 (phases) + 2 = 12
        self.assertEqual(obs.shape, (12,))
        self.assertEqual(obs.dtype, np.float32)
        self.assertEqual(info["step"], 0)
        self.assertEqual(info["active_green_phase"], 0)
        env.close()
        self.assertFalse(env.is_running)

    def test_reset_rejects_missing_tls_id(self) -> None:
        """Verify ValueError raised when configured TLS ID does not exist in network."""
        mock = MockTraciModule(available_tls=["OTHER_TLS"])
        env = SumoEnvironment(
            config=self.config,
            net_file="dummy.net.xml",
            route_file="dummy.rou.xml",
            traci_module=mock,
            sumo_binary="sumo",
        )
        with self.assertRaises(ValueError) as ctx:
            env.reset()
        self.assertIn("not found in network", str(ctx.exception))
        self.assertFalse(env.is_running)

    def test_reset_rejects_missing_lanes(self) -> None:
        """Verify ValueError raised when incoming or exit lanes are missing."""
        mock = MockTraciModule(available_lanes=["lane_0"])  # lane_1 missing
        env = SumoEnvironment(
            config=self.config,
            net_file="dummy.net.xml",
            route_file="dummy.rou.xml",
            traci_module=mock,
            sumo_binary="sumo",
        )
        with self.assertRaises(ValueError) as ctx:
            env.reset()
        self.assertIn("missing from network", str(ctx.exception))

    def test_step_safety_enforcement_min_green(self) -> None:
        """Verify controller cannot force phase switch before min green expires."""
        env = SumoEnvironment(
            config=self.config,
            net_file="dummy.net.xml",
            route_file="dummy.rou.xml",
            traci_module=self.mock_traci,
            observation_builder=self.obs_builder,
            reward_calculator=self.reward_calc,
            exit_lanes=["exit_0"],
            sumo_binary="sumo",
        )
        env.reset()

        # Step 1: Action 1 requests green phase 2 (current is 0)
        # min_green is 10.0s, elapsed is 0.0s -> request must be rejected!
        obs, reward, terminated, truncated, info = env.step(action=1)
        self.assertFalse(info["action_accepted"])
        self.assertIn("Minimum green not satisfied", info["action_reason"])
        self.assertEqual(info["active_green_phase"], 0)
        # TraCI traffic light phase must still be 0!
        self.assertEqual(self.mock_traci.trafficlight.current_phase, 0)
        env.close()

    def test_step_executes_transition_after_min_green(self) -> None:
        """Verify transition is executed once min green is satisfied."""
        env = SumoEnvironment(
            config=self.config,
            net_file="dummy.net.xml",
            route_file="dummy.rou.xml",
            traci_module=self.mock_traci,
            observation_builder=self.obs_builder,
            reward_calculator=self.reward_calc,
            sumo_binary="sumo",
        )
        env.reset()

        # Step 10 times with action 0 (holding phase 0)
        for _ in range(10):
            env.step(action=0)

        # Now elapsed_green is 10.0s -> request switch to phase 2 (action 1)
        obs, reward, terminated, truncated, info = env.step(action=1)
        self.assertTrue(info["action_accepted"])
        self.assertEqual(info["active_green_phase"], 2)
        # TraCI phase was updated to 2
        self.assertEqual(self.mock_traci.trafficlight.current_phase, 2)
        env.close()

    def test_action_bounds_validation(self) -> None:
        """Verify out-of-bounds or non-integer actions raise ValueError."""
        env = SumoEnvironment(
            config=self.config,
            net_file="dummy.net.xml",
            route_file="dummy.rou.xml",
            traci_module=self.mock_traci,
            sumo_binary="sumo",
        )
        env.reset()

        with self.assertRaises(ValueError):
            env.step(action=-1)
        with self.assertRaises(ValueError):
            env.step(action=2)  # only actions 0 and 1 are valid
        with self.assertRaises(ValueError):
            env.step(action=True)  # type: ignore
        env.close()

    def test_context_manager_lifecycle(self) -> None:
        """Verify context manager automatically closes TraCI session upon exit."""
        env = SumoEnvironment(
            config=self.config,
            net_file="dummy.net.xml",
            route_file="dummy.rou.xml",
            traci_module=self.mock_traci,
            sumo_binary="sumo",
        )
        with env:
            env.reset()
            self.assertTrue(env.is_running)

        self.assertFalse(env.is_running)


class TestSumoEnvironmentRealIntegration(unittest.TestCase):
    """Integration test using the real SUMO binary and smoke test files."""

    def test_real_sumo_launch_and_tls_validation(self) -> None:
        """Verify real SUMO launches and correctly reports missing TLS ID in smoke network."""
        # The smoke network (tests/smoke.net.xml) has NO traffic lights (priority grid).
        # When SumoEnvironment connects to real SUMO, it must detect that TLS 'J1' is missing
        # and raise a ValueError while cleanly shutting down the TraCI process.
        config = IntersectionConfig(
            tls_id="J1",
            incoming_lanes=["A1B1_0"],
            green_phase_indices=[0],
            min_green_seconds=10.0,
            max_green_seconds=30.0,
        )
        env = SumoEnvironment(
            config=config,
            net_file="tests/smoke.net.xml",
            route_file="tests/smoke.rou.xml",
        )

        with self.assertRaises(ValueError) as ctx:
            env.reset()

        self.assertIn("Configured tls_id 'J1' not found in network", str(ctx.exception))
        # Verify TraCI process was closed cleanly without leaving an active session
        self.assertFalse(env.is_running)


class TestSumoEnvironmentRealTLSIntegration(unittest.TestCase):
    """Real SUMO integration tests exercising genuine traffic-light clearance execution."""

    def setUp(self) -> None:
        self.fixture_net = os.path.abspath("tests/fixtures/test_tls.net.xml")
        self.fixture_rou = os.path.abspath("tests/fixtures/test_tls.rou.xml")
        self.config = IntersectionConfig(
            tls_id="A0",
            incoming_lanes=["bottom0A0_0", "left0A0_0", "right0A0_0", "top0A0_0"],
            green_phase_indices=[0, 2],
            min_green_seconds=5.0,
            max_green_seconds=45.0,
            control_interval_seconds=1.0,
            clearance_handled_by_sumo=True,
        )
        self.env = None

    def tearDown(self) -> None:
        if self.env is not None:
            self.env.close()

    def test_real_tls_clearance_execution_and_safety(self) -> None:
        """Verify real SUMO executes yellow clearance for 3.0s before switching green phases."""
        self.env = SumoEnvironment(
            config=self.config,
            net_file=self.fixture_net,
            route_file=self.fixture_rou,
            exit_lanes=["A0bottom0_0", "A0left0_0", "A0right0_0", "A0top0_0"],
        )

        # 1. Reset: verify initial state
        obs, info = self.env.reset(seed=123)
        self.assertTrue(self.env.is_running)
        self.assertEqual(info["active_green_phase"], 0)
        self.assertFalse(info["min_green_satisfied"])
        # Expected vector dim: 4*4 lanes + 2 phases + 2 = 20
        self.assertEqual(obs.shape, (20,))
        self.assertTrue(np.all(np.isfinite(obs)))

        # 2. Safety constraint: Request phase switch before min green elapses (elapsed green = 0)
        # Action 1 requests Green Phase 2
        obs, reward, term, trunc, info = self.env.step(action=1)
        self.assertFalse(info["action_accepted"])
        self.assertIn("Minimum green not satisfied", info["action_reason"])
        self.assertEqual(info["active_green_phase"], 0)
        self.assertFalse(info["clearance_executed"])

        # 3. Hold phase 0 until min green (5.0s) is satisfied
        # 1 step already executed (elapsed = 1.0s); need 4 more steps of action 0
        for _ in range(4):
            obs, reward, term, trunc, info = self.env.step(action=0)
            self.assertTrue(info["action_accepted"])

        self.assertTrue(info["min_green_satisfied"])
        self.assertEqual(info["active_green_phase"], 0)

        # 4. Legal transition: Now request switch to Green Phase 2
        # In test_tls.net.xml, intermediate Phase 1 is Yellow for 3.0s!
        # SumoEnvironment MUST actively command Phase 1 for 3.0s before serving Phase 2!
        obs, reward, term, trunc, info = self.env.step(action=1)

        self.assertTrue(info["action_accepted"])
        self.assertTrue(info["clearance_executed"])
        self.assertEqual(info["clearance_phases"], [1])
        self.assertAlmostEqual(info["clearance_duration_seconds"], 3.0, places=2)
        self.assertEqual(info["active_green_phase"], 2)
        # Observation must be at valid green decision point
        self.assertEqual(obs.shape, (20,))
        self.assertTrue(np.all(np.isfinite(obs)))
        # Total simulation time: 5s initial green + 3s clearance + 1s green = 9.0s exactly
        self.assertEqual(info["simulation_time"], 9.0)

        # 5. Clean teardown
        self.env.close()
        self.assertFalse(self.env.is_running)


if __name__ == "__main__":
    unittest.main()
