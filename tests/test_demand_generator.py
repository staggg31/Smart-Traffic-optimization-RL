"""Unit and integration tests for traffic demand generator."""

import os
import unittest
import xml.etree.ElementTree as ET

from config.schema import IntersectionConfig
from controllers.fixed_time import FixedTimeController
from environment.sumo_environment import SumoEnvironment
from evaluation.runner import run_simulation_experiment
from scripts.generate_demand import (
    DEMAND_LEVELS,
    VALID_ROUTES,
    generate_benchmark_scenarios,
    generate_traffic_demand,
)


class TestDemandGenerator(unittest.TestCase):
    """Test suite for traffic demand generation script."""

    def setUp(self) -> None:
        self.test_out_dir = "data/routes_test"
        os.makedirs(self.test_out_dir, exist_ok=True)

    def test_invalid_parameters(self) -> None:
        """Reject non-positive flow rates or durations."""
        with self.assertRaises(ValueError):
            generate_traffic_demand("dummy.rou.xml", total_flow_veh_per_hr=-100)

        with self.assertRaises(ValueError):
            generate_traffic_demand("dummy.rou.xml", total_flow_veh_per_hr=0)

        with self.assertRaises(ValueError):
            generate_traffic_demand("dummy.rou.xml", total_flow_veh_per_hr=400, duration_seconds=0)

    def test_seed_reproducibility(self) -> None:
        """Verify identical XML generation across identical random seeds."""
        f1 = os.path.join(self.test_out_dir, "test_seed1.rou.xml")
        f2 = os.path.join(self.test_out_dir, "test_seed2.rou.xml")

        stats1 = generate_traffic_demand(f1, total_flow_veh_per_hr=400, duration_seconds=60, seed=123)
        stats2 = generate_traffic_demand(f2, total_flow_veh_per_hr=400, duration_seconds=60, seed=123)

        self.assertEqual(stats1["total_vehicles"], stats2["total_vehicles"])

        with open(f1, "r", encoding="utf-8") as fp1, open(f2, "r", encoding="utf-8") as fp2:
            self.assertEqual(fp1.read(), fp2.read())

    def test_xml_structure_and_routes(self) -> None:
        """Verify generated XML follows valid SUMO routes schema and valid network turn connections."""
        f = os.path.join(self.test_out_dir, "test_structure.rou.xml")
        stats = generate_traffic_demand(f, total_flow_veh_per_hr=800, duration_seconds=120, seed=42)

        tree = ET.parse(f)
        root = tree.getroot()
        self.assertEqual(root.tag, "routes")

        # Must have vType
        vtypes = root.findall("vType")
        self.assertEqual(len(vtypes), 1)
        self.assertEqual(vtypes[0].get("id"), "car")

        # Check vehicle elements
        vehicles = root.findall("vehicle")
        self.assertEqual(len(vehicles), stats["total_vehicles"])

        veh_ids = set()
        prev_depart = -1.0
        for v in vehicles:
            vid = v.get("id")
            self.assertNotIn(vid, veh_ids)
            veh_ids.add(vid)

            depart = float(v.get("depart"))
            self.assertGreaterEqual(depart, prev_depart)
            prev_depart = depart

    def test_real_sumo_execution_on_generated_demand(self) -> None:
        """Verify real SUMO loads and completes a generated demand scenario."""
        f = os.path.join(self.test_out_dir, "test_sumo_exec.rou.xml")
        stats = generate_traffic_demand(f, total_flow_veh_per_hr=400, duration_seconds=60, seed=99)
        total_veh = stats["total_vehicles"]

        cfg = IntersectionConfig(
            tls_id="C",
            incoming_lanes=["N_in_0", "N_in_1", "S_in_0", "S_in_1", "E_in_0", "E_in_1", "W_in_0", "W_in_1"],
            green_phase_indices=[0, 2],
            min_green_seconds=5.0,
            max_green_seconds=45.0,
            control_interval_seconds=1.0,
            yellow_seconds=3.0,
            all_red_seconds=0.0,
            clearance_handled_by_sumo=True,
            exit_lanes=["N_out_0", "N_out_1", "S_out_0", "S_out_1", "E_out_0", "E_out_1", "W_out_0", "W_out_1"],
        )
        net = os.path.abspath("environment/single_intersection.net.xml")

        env = SumoEnvironment(cfg, net, os.path.abspath(f), max_steps=200)
        ctrl = FixedTimeController.from_config(cfg, default_green_seconds=42.0)
        res = run_simulation_experiment(env, ctrl, close_env=True)

        self.assertTrue(res.terminated or res.truncated)
        self.assertEqual(res.total_throughput_vehicles, float(total_veh))


if __name__ == "__main__":
    unittest.main()
