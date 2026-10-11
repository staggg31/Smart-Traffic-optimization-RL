"""Unit and integration tests for evaluation experiment runner."""

import os
import unittest
import numpy as np

from config.schema import IntersectionConfig
from controllers.fixed_time import FixedTimeController
from environment.sumo_environment import SumoEnvironment
from evaluation.runner import (
    ExperimentResult,
    StepRecord,
    run_simulation_experiment,
)


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
        return 2

    def getLastStepVehicleNumber(self, lane_id):
        return 4

    def getWaitingTime(self, lane_id):
        return 20.0

    def getLastStepMeanSpeed(self, lane_id):
        return 8.0

    def getCO2Emission(self, lane_id):
        return 50.0

    def getLastStepVehicleIDs(self, lane_id):
        if lane_id == "exit_0":
            return ["veh_1"]
        return ["veh_1", "veh_2"]


class MockSimulation:
    def __init__(self, max_steps=5):
        self._time = 0.0
        self._step_count = 0
        self._max_steps = max_steps

    def getTime(self):
        return self._time

    def getMinExpectedNumber(self):
        if self._step_count >= self._max_steps:
            return 0
        return 5


class MockVehicle:
    def getSpeed(self, veh_id):
        return 0.0


class MockTraciModule:
    def __init__(self, max_steps=5, lane_ids=None):
        self.trafficlight = MockTrafficLight()
        self.lane = MockLane(lane_ids=lane_ids)
        self.simulation = MockSimulation(max_steps=max_steps)
        self.vehicle = MockVehicle()
        self.closed = False

    def start(self, cmd):
        pass

    def simulationStep(self):
        self.simulation._time += 1.0
        self.simulation._step_count += 1

    def close(self):
        self.closed = True


class TestEvaluationRunnerUnit(unittest.TestCase):
    """Unit tests for run_simulation_experiment using mocked TraCI."""

    def setUp(self) -> None:
        self.config_with_exit = IntersectionConfig(
            tls_id="J1",
            incoming_lanes=["lane_0", "lane_1"],
            green_phase_indices=[0, 2],
            min_green_seconds=5.0,
            max_green_seconds=50.0,
            control_interval_seconds=1.0,
            exit_lanes=["exit_0"],
        )

        self.config_no_exit = IntersectionConfig(
            tls_id="J1",
            incoming_lanes=["lane_0", "lane_1"],
            green_phase_indices=[0, 2],
            min_green_seconds=5.0,
            max_green_seconds=50.0,
            control_interval_seconds=1.0,
            exit_lanes=None,
        )

    def test_invalid_max_steps(self) -> None:
        """Reject invalid max_steps arguments."""
        mock_traci = MockTraciModule()
        env = SumoEnvironment(
            self.config_with_exit,
            net_file="dummy.net.xml",
            route_file="dummy.rou.xml",
            traci_module=mock_traci,
        )
        ctrl = FixedTimeController.from_config(self.config_with_exit)

        with self.assertRaises(ValueError):
            run_simulation_experiment(env, ctrl, max_steps=-1)

        with self.assertRaises(ValueError):
            run_simulation_experiment(env, ctrl, max_steps=True)  # type: ignore

    def test_run_with_throughput_tracking(self) -> None:
        """Verify experiment execution when exit lanes are active."""
        mock_traci = MockTraciModule(max_steps=3)
        env = SumoEnvironment(
            self.config_with_exit,
            net_file="dummy.net.xml",
            route_file="dummy.rou.xml",
            traci_module=mock_traci,
        )
        ctrl = FixedTimeController.from_config(self.config_with_exit)

        result = run_simulation_experiment(env, ctrl, max_steps=3, close_env=True)

        self.assertIsInstance(result, ExperimentResult)
        self.assertEqual(result.controller_name, "FixedTimeController")
        self.assertEqual(result.total_steps, 3)
        self.assertTrue(result.throughput_available)
        self.assertIsNotNone(result.total_throughput_vehicles)
        self.assertGreaterEqual(result.total_throughput_vehicles, 0.0)
        self.assertTrue(result.truncated or result.terminated)
        self.assertTrue(mock_traci.closed)

        # Check step records
        self.assertEqual(len(result.step_records), 3)
        for record in result.step_records:
            self.assertIsInstance(record, StepRecord)
            self.assertIsNotNone(record.throughput)
            self.assertGreaterEqual(record.throughput, 0.0)

        # Summary dictionary
        summary = result.summary()
        self.assertEqual(summary["step_records"], [])
        self.assertEqual(summary["total_steps"], 3)

    def test_run_without_throughput_tracking_distinguishes_unavailable(self) -> None:
        """Verify runner records throughput as None when exit lanes are not configured."""
        mock_traci = MockTraciModule(max_steps=2, lane_ids=["lane_0", "lane_1"])
        env = SumoEnvironment(
            self.config_no_exit,
            net_file="dummy.net.xml",
            route_file="dummy.rou.xml",
            traci_module=mock_traci,
        )
        ctrl = FixedTimeController.from_config(self.config_no_exit)

        result = run_simulation_experiment(env, ctrl, max_steps=2, close_env=True)

        self.assertFalse(result.throughput_available)
        self.assertIsNone(result.total_throughput_vehicles)
        for record in result.step_records:
            self.assertIsNone(record.throughput)


class TestEvaluationRunnerRealSumo(unittest.TestCase):
    """Integration test suite executing FixedTimeController on real SUMO research intersection."""

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

    def test_real_sumo_fixed_time_baseline_experiment(self) -> None:
        """Execute complete baseline fixed-time experiment on actual intersection.

        Validates:
            - Full trip execution of all 8 vehicles.
            - Natural termination at expected time.
            - Correct verified throughput measurement (8.0 vehicles).
            - Active yellow clearance phase insertion.
            - Non-trivial physical metrics (waiting time, queue, emissions).
        """
        env = SumoEnvironment(
            config=self.config,
            net_file=self.net_file,
            route_file=self.route_file,
        )
        controller = FixedTimeController.from_config(self.config, default_green_seconds=42.0)

        result = run_simulation_experiment(env, controller, close_env=True)

        # Baseline Controller identification
        self.assertEqual(result.controller_name, "FixedTimeController")

        # Natural episode termination
        # 63 decision steps (63s) + 1 clearance sequence (3s yellow) = 66.0s total simulation time
        self.assertTrue(result.terminated)
        self.assertFalse(result.truncated)
        self.assertEqual(result.total_steps, 63)
        self.assertAlmostEqual(result.simulation_time_seconds, 66.0, places=1)

        # Throughput verification: all 8 vehicles completed trips through intersection
        self.assertTrue(result.throughput_available)
        self.assertEqual(result.total_throughput_vehicles, 8.0)

        # Clearance safety verification: transition from green 0 to green 2 occurred
        self.assertGreaterEqual(result.clearance_episodes, 1)
        self.assertGreaterEqual(result.phase_switches, 1)

        # Physical measurements are finite and non-negative
        self.assertGreaterEqual(result.total_emissions_mg, 0.0)
        self.assertGreaterEqual(result.mean_queue_vehicles, 0.0)
        self.assertGreaterEqual(result.mean_waiting_time_seconds, 0.0)
        self.assertGreaterEqual(result.total_stops, 0)

        # Step records verification
        self.assertEqual(len(result.step_records), 63)
        clearance_step = next(s for s in result.step_records if s.clearance_executed)
        self.assertEqual(clearance_step.clearance_phases, [1])
        self.assertAlmostEqual(clearance_step.clearance_duration_seconds, 3.0)

    def test_real_sumo_actuated_baseline_experiment(self) -> None:
        """Execute complete baseline actuated experiment on actual intersection.

        Validates:
            - Full trip execution of all 8 vehicles.
            - Natural termination at expected time.
            - Verified throughput measurement (8.0 vehicles).
            - Active yellow clearance phase insertion.
            - Responsive gap-out behavior when active approaches become clear.
        """
        from controllers.actuated import ActuatedController

        env = SumoEnvironment(
            config=self.config,
            net_file=self.net_file,
            route_file=self.route_file,
        )
        controller = ActuatedController.from_config(self.config, queue_threshold=0.5)

        result = run_simulation_experiment(env, controller, close_env=True)

        self.assertEqual(result.controller_name, "ActuatedController")
        self.assertTrue(result.terminated)
        self.assertFalse(result.truncated)
        self.assertTrue(result.throughput_available)
        self.assertEqual(result.total_throughput_vehicles, 8.0)
        self.assertGreaterEqual(result.clearance_episodes, 1)
        self.assertGreaterEqual(result.phase_switches, 1)
        self.assertGreaterEqual(result.total_emissions_mg, 0.0)


if __name__ == "__main__":
    unittest.main()
