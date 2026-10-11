"""Unit tests for FastAPI backend service in api/main.py."""

import unittest
from fastapi import HTTPException

from api.main import (
    get_system_status,
    get_model_metadata,
    get_training_progress,
    get_evaluation_scenarios,
    get_evaluation_summary,
    get_evaluation_raw,
    get_cross_scenario_comparison,
)


class TestBackendAPI(unittest.TestCase):
    """Test suite for backend API endpoints."""

    def test_status_endpoint(self) -> None:
        """Verify get_system_status returns operational status and safety constraints."""
        data = get_system_status()
        self.assertEqual(data["status"], "operational")
        self.assertTrue(data["model"]["available"])
        self.assertEqual(data["safety_constraints"]["min_green_seconds"], 5.0)
        self.assertEqual(data["safety_constraints"]["yellow_clearance_seconds"], 3.0)
        self.assertIn("waiting_metric_explanation", data)

    def test_model_metadata_endpoint(self) -> None:
        """Verify get_model_metadata returns valid PPO metadata."""
        data = get_model_metadata()
        self.assertEqual(data["total_timesteps"], 30000)
        self.assertEqual(data["learning_rate"], 0.0003)
        self.assertEqual(data["n_steps"], 128)

    def test_training_progress_endpoint(self) -> None:
        """Verify get_training_progress returns parsed rows from progress.csv."""
        data = get_training_progress()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 50)
        first_row = data[0]
        self.assertIn("timesteps", first_row)
        self.assertIn("loss", first_row)
        self.assertIn("ep_rew_mean", first_row)

    def test_evaluations_scenarios_endpoint(self) -> None:
        """Verify get_evaluation_scenarios returns all 3 held-out scenarios."""
        data = get_evaluation_scenarios()
        self.assertEqual(len(data), 3)
        scenario_ids = [s["id"] for s in data]
        self.assertIn("eval_heldout_medium_301", scenario_ids)
        self.assertIn("eval_heldout_medium_302", scenario_ids)
        self.assertIn("eval_heldout_medium_303", scenario_ids)

    def test_evaluations_summary_endpoint(self) -> None:
        """Verify get_evaluation_summary returns valid summary or raises HTTPException for bad id."""
        data = get_evaluation_summary("eval_heldout_medium_301")
        self.assertIn("results", data)
        results = data["results"]
        self.assertIn("FixedTimeController", results)
        self.assertIn("ActuatedController", results)
        self.assertIn("PPOController", results)

        # Rejection of invalid scenario raises HTTPException(400)
        with self.assertRaises(HTTPException) as ctx:
            get_evaluation_summary("invalid_scenario")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_evaluations_raw_endpoint(self) -> None:
        """Verify get_evaluation_raw returns raw records list."""
        data = get_evaluation_raw("eval_heldout_medium_301")
        self.assertEqual(len(data), 9)

    def test_evaluations_comparison_endpoint(self) -> None:
        """Verify get_cross_scenario_comparison aggregates all scenarios."""
        data = get_cross_scenario_comparison()
        self.assertIn("scenarios", data)
        self.assertEqual(len(data["scenarios"]), 3)


if __name__ == "__main__":
    unittest.main()
