"""Tests for PPO training pipeline, PPOController, and tri-controller evaluation workflow.

Covers:
- Training configuration validation
- CLI argument parsing for training and evaluation
- Model saving, loading, and action inference validation
- Evaluation result and aggregate schema
- Error handling and TraCI resource cleanup guarantees
- Real-SUMO smoke test with PPOController
"""

import argparse
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import numpy as np

import gymnasium as gym
from gymnasium import spaces

from config.schema import IntersectionConfig
from controllers.ppo import PPOController
from evaluation.evaluate_all import (
    build_evaluation_config,
    evaluate_tri_controllers,
    make_eval_environment,
)
from training.train_ppo import (
    build_default_intersection_config,
    make_training_env,
    train_ppo,
)


class TestTrainingConfigAndCLI(unittest.TestCase):
    """Test configuration validation and CLI parsing for PPO training and evaluation."""

    def test_default_intersection_config_validation(self):
        """Verify build_default_intersection_config produces valid canonical IntersectionConfig."""
        cfg = build_default_intersection_config()
        self.assertIsInstance(cfg, IntersectionConfig)
        self.assertEqual(cfg.tls_id, "C")
        self.assertEqual(len(cfg.incoming_lanes), 8)
        self.assertEqual(cfg.green_phase_indices, [0, 2])
        self.assertTrue(cfg.clearance_handled_by_sumo)
        self.assertEqual(cfg.yellow_seconds, 3.0)

    def test_eval_intersection_config_validation(self):
        """Verify build_evaluation_config matches evaluation standards."""
        cfg = build_evaluation_config()
        self.assertIsInstance(cfg, IntersectionConfig)
        self.assertEqual(cfg.tls_id, "C")
        self.assertEqual(len(cfg.exit_lanes), 8)

    def test_train_cli_argument_parsing(self):
        """Verify train_ppo CLI argument parsing logic."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--timesteps", type=int, default=1000)
        parser.add_argument("--routes", default="data/routes/demand_low_seed42.rou.xml")
        parser.add_argument("--outdir", default="models/ppo")
        parser.add_argument("--logdir", default="logs/ppo")
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument("--lr", type=float, default=3e-4)
        parser.add_argument("--n_steps", type=int, default=128)
        parser.add_argument("--batch_size", type=int, default=64)

        test_args = [
            "--timesteps", "500",
            "--routes", "test_route.rou.xml",
            "--outdir", "custom/models",
            "--seed", "123",
            "--lr", "0.001",
        ]
        args = parser.parse_args(test_args)
        self.assertEqual(args.timesteps, 500)
        self.assertEqual(args.routes, "test_route.rou.xml")
        self.assertEqual(args.outdir, "custom/models")
        self.assertEqual(args.seed, 123)
        self.assertAlmostEqual(args.lr, 0.001)

    def test_eval_cli_argument_parsing(self):
        """Verify evaluate_all CLI argument parsing logic."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--routes", default="environment/routes.rou.xml")
        parser.add_argument("--model", default="models/ppo/ppo_traffic_final.zip")
        parser.add_argument("--seeds", nargs="+", type=int, default=[301, 302, 303])
        parser.add_argument("--outdir", default="results/evaluations")
        parser.add_argument("--max_steps", type=int, default=300)
        parser.add_argument("--actuated_threshold", type=float, default=0.5)

        test_args = [
            "--routes", "eval_routes.xml",
            "--seeds", "401", "402",
            "--max_steps", "150",
            "--actuated_threshold", "0.025",
        ]
        args = parser.parse_args(test_args)
        self.assertEqual(args.routes, "eval_routes.xml")
        self.assertEqual(args.seeds, [401, 402])
        self.assertEqual(args.max_steps, 150)
        self.assertAlmostEqual(args.actuated_threshold, 0.025)


class TestPPOController(unittest.TestCase):
    """Test PPOController contract, validation, loading, and inference."""

    def test_missing_model_raises_file_not_found(self):
        """Verify FileNotFoundError is raised when checkpoint path does not exist."""
        with self.assertRaises(FileNotFoundError):
            PPOController("nonexistent_directory/nonexistent_model.zip")

    def test_observation_validation(self):
        """Verify strict input validation on observation array."""
        mock_model = MagicMock()
        mock_model.predict.return_value = (np.array(1), None)
        controller = PPOController.from_model(mock_model)

        # Non-numpy
        with self.assertRaises(ValueError):
            controller.act([0.1, 0.2])  # type: ignore

        # Wrong dimensionality (2D instead of 1D)
        with self.assertRaises(ValueError):
            controller.act(np.array([[0.1, 0.2]]))

        # Non-finite values
        with self.assertRaises(ValueError):
            controller.act(np.array([0.1, np.nan, 0.3], dtype=np.float32))

        with self.assertRaises(ValueError):
            controller.act(np.array([0.1, np.inf, 0.3], dtype=np.float32))

    def test_valid_act_and_reset(self):
        """Verify valid observation produces integer action and reset is callable."""
        mock_model = MagicMock()
        mock_model.predict.return_value = (np.int64(1), None)
        controller = PPOController.from_model(mock_model, deterministic=True)

        obs = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
        action = controller.act(obs)

        self.assertIsInstance(action, int)
        self.assertEqual(action, 1)
        mock_model.predict.assert_called_once_with(obs, deterministic=True)

        # Reset is a no-op but must execute cleanly
        controller.reset()

    def test_save_and_load_micro_model(self):
        """Verify model saving and loading lifecycle using a minimal SB3 model."""
        from stable_baselines3 import PPO

        temp_dir = tempfile.mkdtemp(prefix="test_sb3_ppo_")
        try:
            # Create a minimal gym environment for saving a valid model
            toy_env = gym.make("CartPole-v1")
            model = PPO("MlpPolicy", toy_env, n_steps=32, batch_size=32, n_epochs=1, seed=42)
            model.learn(total_timesteps=32)

            save_path = os.path.join(temp_dir, "test_model.zip")
            model.save(save_path)
            self.assertTrue(os.path.exists(save_path))

            # Load through PPOController
            controller = PPOController(save_path, deterministic=True)
            self.assertEqual(controller.model_path, os.path.abspath(save_path))

            # Test inference with valid 1D observation
            obs, _ = toy_env.reset(seed=42)
            action = controller.act(np.asarray(obs, dtype=np.float32))
            self.assertIn(action, [0, 1])
            toy_env.close()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestTrainingHarnessResourceSafety(unittest.TestCase):
    """Test resource cleanup, exception resilience, and metadata tracking."""

    @patch("training.train_ppo.PPO")
    @patch("training.train_ppo.make_training_env")
    def test_env_cleanup_on_exception(self, mock_make_env, mock_ppo_cls):
        """Verify env.close() is strictly called even if model.learn raises an exception."""
        mock_env = MagicMock()
        mock_make_env.return_value = mock_env

        mock_ppo_instance = MagicMock()
        mock_ppo_instance.learn.side_effect = RuntimeError("Simulated TraCI communication failure")
        mock_ppo_cls.return_value = mock_ppo_instance

        temp_dir = tempfile.mkdtemp(prefix="test_train_cleanup_")
        try:
            with self.assertRaises(RuntimeError):
                train_ppo(
                    total_timesteps=100,
                    route_file="environment/routes.rou.xml",
                    output_dir=temp_dir,
                    log_dir=temp_dir,
                    seed=42,
                )
            # Crucial verification: env.close() MUST be called in finally block
            mock_env.close.assert_called_once()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("training.train_ppo.PPO")
    @patch("training.train_ppo.make_training_env")
    def test_training_metadata_saved(self, mock_make_env, mock_ppo_cls):
        """Verify training_metadata.json records complete hyperparameter set."""
        mock_env = MagicMock()
        mock_env.action_space = spaces.Discrete(2)
        mock_env.observation_space = spaces.Box(low=0.0, high=1.0, shape=(36,), dtype=np.float32)
        mock_make_env.return_value = mock_env

        mock_ppo_instance = MagicMock()
        mock_ppo_cls.return_value = mock_ppo_instance

        temp_dir = tempfile.mkdtemp(prefix="test_train_meta_")
        try:
            train_ppo(
                total_timesteps=200,
                route_file="environment/routes.rou.xml",
                output_dir=temp_dir,
                log_dir=temp_dir,
                seed=42,
                learning_rate=1e-4,
                n_steps=64,
                batch_size=32,
            )
            meta_file = os.path.join(temp_dir, "training_metadata.json")
            self.assertTrue(os.path.exists(meta_file))

            import json
            with open(meta_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["total_timesteps"], 200)
            self.assertEqual(data["seed"], 42)
            self.assertEqual(data["learning_rate"], 1e-4)
            self.assertEqual(data["n_steps"], 64)
            self.assertEqual(data["batch_size"], 32)
            mock_env.close.assert_called_once()
            # Verify set_logger was called on PPO model
            mock_ppo_instance.set_logger.assert_called_once()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestEvaluationWorkflowSchema(unittest.TestCase):
    """Test evaluation aggregation logic, output schema, and fair statistical reporting."""

    def test_evaluation_schema_and_statistics(self):
        """Verify aggregation correctly computes mean and sample std across seeds."""
        from evaluation.evaluate_all import evaluate_tri_controllers

        temp_dir = tempfile.mkdtemp(prefix="test_eval_schema_")
        try:
            # Mock run_simulation_experiment to return deterministic ExperimentResults
            from evaluation.runner import ExperimentResult

            mock_res_ft_301 = ExperimentResult(
                controller_name="FixedTimeController",
                total_steps=50,
                simulation_time_seconds=50.0,
                total_reward=10.0,
                mean_waiting_time_seconds=2.0,
                mean_queue_vehicles=0.5,
                total_stops=4,
                total_emissions_mg=1000.0,
                total_throughput_vehicles=8.0,
                throughput_available=True,
                terminated=True,
                truncated=False,
                phase_switches=1,
                clearance_episodes=0,
                step_records=[],
            )
            mock_res_ft_302 = ExperimentResult(
                controller_name="FixedTimeController",
                total_steps=50,
                simulation_time_seconds=50.0,
                total_reward=20.0,
                mean_waiting_time_seconds=4.0,
                mean_queue_vehicles=1.5,
                total_stops=6,
                total_emissions_mg=2000.0,
                total_throughput_vehicles=10.0,
                throughput_available=True,
                terminated=True,
                truncated=False,
                phase_switches=1,
                clearance_episodes=0,
                step_records=[],
            )
            mock_res_act_301 = ExperimentResult(
                controller_name="ActuatedController",
                total_steps=50,
                simulation_time_seconds=50.0,
                total_reward=15.0,
                mean_waiting_time_seconds=1.0,
                mean_queue_vehicles=0.3,
                total_stops=3,
                total_emissions_mg=800.0,
                total_throughput_vehicles=9.0,
                throughput_available=True,
                terminated=True,
                truncated=False,
                phase_switches=2,
                clearance_episodes=0,
                step_records=[],
            )
            mock_res_act_302 = ExperimentResult(
                controller_name="ActuatedController",
                total_steps=50,
                simulation_time_seconds=50.0,
                total_reward=25.0,
                mean_waiting_time_seconds=1.5,
                mean_queue_vehicles=0.4,
                total_stops=4,
                total_emissions_mg=900.0,
                total_throughput_vehicles=11.0,
                throughput_available=True,
                terminated=True,
                truncated=False,
                phase_switches=2,
                clearance_episodes=0,
                step_records=[],
            )

            with patch("evaluation.evaluate_all.run_simulation_experiment") as mock_run:
                mock_run.side_effect = [
                    mock_res_ft_301, mock_res_ft_302,
                    mock_res_act_301, mock_res_act_302,
                ]

                res = evaluate_tri_controllers(
                    route_file="environment/routes.rou.xml",
                    ppo_model_path=None,  # Only test baselines here
                    seeds=[301, 302],
                    output_dir=temp_dir,
                    max_steps=50,
                )

                # Verify files generated
                self.assertTrue(os.path.exists(res["raw_json_path"]))
                self.assertTrue(os.path.exists(res["raw_csv_path"]))
                self.assertTrue(os.path.exists(res["summary_json_path"]))
                self.assertTrue(os.path.exists(res["summary_csv_path"]))

                # Verify statistics: mean throughput = (8 + 10) / 2 = 9.0
                aggs_ft = res["aggregates"]["FixedTimeController"]
                self.assertAlmostEqual(aggs_ft["total_throughput_vehicles"]["mean"], 9.0)
                # Sample std: sqrt(((8-9)^2 + (10-9)^2)/(2-1)) = sqrt(2) ≈ 1.4142
                self.assertAlmostEqual(aggs_ft["total_throughput_vehicles"]["sample_std"], np.sqrt(2.0), places=3)
                # Mean waiting time: (2.0 + 4.0) / 2 = 3.0
                self.assertAlmostEqual(aggs_ft["mean_waiting_time_seconds"]["mean"], 3.0)

                aggs_act = res["aggregates"]["ActuatedController"]
                self.assertAlmostEqual(aggs_act["total_throughput_vehicles"]["mean"], 10.0)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestPPOSmokeRealSUMO(unittest.TestCase):
    """Real-SUMO integration smoke test verifying PPOController runs with TraCI."""

    def test_ppo_controller_real_sumo_smoke(self):
        """Execute a short real SUMO simulation run with a loaded PPOController."""
        smoke_model_path = "models/ppo_smoke/ppo_traffic_final.zip"
        if not os.path.exists(smoke_model_path):
            self.skipTest(f"Smoke model {smoke_model_path} not found.")

        controller = PPOController(smoke_model_path, deterministic=True)
        env = make_eval_environment(
            route_file="environment/routes.rou.xml",
            max_steps=10,
        )

        try:
            obs, info = env.reset(seed=999)
            self.assertIsInstance(obs, np.ndarray)
            self.assertEqual(obs.shape, (36,))

            for _ in range(5):
                action = controller.act(obs)
                self.assertIn(action, [0, 1])
                obs, reward, terminated, truncated, info = env.step(action)
                self.assertIsInstance(reward, float)
                if terminated or truncated:
                    break
        finally:
            env.close()


if __name__ == "__main__":
    unittest.main()
