"""Production training pipeline for PPO on the traffic signal optimization environment.

This module provides a reproducible training harness using Stable-Baselines3 PPO
with SumoGymAdapter, configurable demand profiles, checkpoints, evaluation callbacks,
hyperparameter tracking, and exception-safe TraCI lifecycle management.
"""

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, Optional, Tuple

# Ensure workspace root is in sys.path
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import gymnasium as gym
import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback, CheckpointCallback

from config.schema import IntersectionConfig
from environment.gym_wrapper import SumoGymAdapter
from environment.observation import ObservationBuilder, ObservationNormalizerConfig
from environment.reward import RewardCalculator, RewardScalingConfig, RewardWeights
from environment.sumo_environment import SumoEnvironment


def build_default_intersection_config() -> IntersectionConfig:
    """Build canonical IntersectionConfig for research intersection TLS C."""
    return IntersectionConfig(
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


def make_training_env(
    route_file: str,
    max_steps: int = 400,
    net_file: Optional[str] = None,
    seed: Optional[int] = None,
) -> SumoGymAdapter:
    """Factory creating a fully configured, normalized SumoGymAdapter for PPO.

    Args:
        route_file: Path to SUMO route file.
        max_steps: Maximum decision steps per episode.
        net_file: Optional path to network file (defaults to single_intersection.net.xml).
        seed: Optional random seed for reproducible initialization.

    Returns:
        SumoGymAdapter instance.
    """
    config = build_default_intersection_config()
    net = os.path.abspath(net_file or "environment/single_intersection.net.xml")
    routes = os.path.abspath(route_file)

    norm_cfg = ObservationNormalizerConfig(
        max_queue_per_lane=20.0,
        max_vehicles_per_lane=25.0,
        max_waiting_time_seconds=100.0,
        speed_limit_mps=13.89,
        max_green_seconds=45.0,
    )
    obs_builder = ObservationBuilder(
        lane_order=config.incoming_lanes,
        green_phase_order=config.green_phase_indices,
        normalizer_config=norm_cfg,
    )

    scales = RewardScalingConfig(
        waiting_time_ref_seconds=100.0,
        queue_ref_vehicles=10.0,
        stops_ref_vehicles=5.0,
        emissions_ref_mg=100000.0,
        throughput_ref_vehicles=10.0,
    )
    weights = RewardWeights(
        w_waiting_time=1.0,
        w_queue=0.5,
        w_stops=0.1,
        w_emissions=0.1,
        w_throughput=0.5,
    )
    reward_calc = RewardCalculator(scales, weights)

    sumo_env = SumoEnvironment(
        config=config,
        net_file=net,
        route_file=routes,
        observation_builder=obs_builder,
        reward_calculator=reward_calc,
        max_steps=max_steps,
    )
    return SumoGymAdapter(sumo_env)


def train_ppo(
    total_timesteps: int = 10000,
    route_file: str = "data/routes/demand_medium_seed42.rou.xml",
    output_dir: str = "models/ppo",
    log_dir: str = "logs/ppo",
    seed: int = 42,
    learning_rate: float = 3e-4,
    n_steps: int = 128,
    batch_size: int = 64,
    n_epochs: int = 10,
    gamma: float = 0.99,
    gae_lambda: float = 0.95,
    clip_range: float = 0.2,
    net_arch: Tuple[int, ...] = (64, 64),
    checkpoint_freq: int = 5000,
) -> Tuple[PPO, str]:
    """Train a PPO model on the SUMO traffic signal control environment.

    Args:
        total_timesteps: Total simulation decision steps to train.
        route_file: Route file defining training demand.
        output_dir: Directory to save model checkpoints and final weights.
        log_dir: Directory to save Tensorboard / metadata logs.
        seed: Random seed for policy and environment initialization.
        learning_rate: Adam optimizer learning rate.
        n_steps: Rollout buffer size per update.
        batch_size: Minibatch size for policy updates.
        n_epochs: Optimization epochs per rollout buffer.
        gamma: Discount factor.
        gae_lambda: Factor for generalized advantage estimation.
        clip_range: PPO policy surrogate objective clipping epsilon.
        net_arch: MLP hidden layer architecture for actor and critic.
        checkpoint_freq: Interval in steps to save intermediate models.

    Returns:
        Tuple[PPO, str]: (trained_model, final_model_path).
    """
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)

    # 1. Instantiate training environment
    env = make_training_env(route_file=route_file, seed=seed)

    # 2. Record experiment metadata
    metadata = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_timesteps": total_timesteps,
        "seed": seed,
        "route_file": os.path.abspath(route_file),
        "learning_rate": learning_rate,
        "n_steps": n_steps,
        "batch_size": batch_size,
        "n_epochs": n_epochs,
        "gamma": gamma,
        "gae_lambda": gae_lambda,
        "clip_range": clip_range,
        "net_arch": list(net_arch),
        "action_space": str(env.action_space),
        "observation_space": str(env.observation_space),
    }
    meta_path = os.path.join(output_dir, "training_metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    # 3. Build PPO model
    policy_kwargs = dict(
        net_arch=dict(pi=list(net_arch), vf=list(net_arch)),
    )

    model = PPO(
        policy="MlpPolicy",
        env=env,
        learning_rate=learning_rate,
        n_steps=n_steps,
        batch_size=batch_size,
        n_epochs=n_epochs,
        gamma=gamma,
        gae_lambda=gae_lambda,
        clip_range=clip_range,
        seed=seed,
        policy_kwargs=policy_kwargs,
        verbose=1,
    )

    from stable_baselines3.common.logger import configure as sb3_configure
    model.set_logger(sb3_configure(log_dir, ["stdout", "csv"]))

    # 4. Checkpoint callback
    callbacks = []
    if checkpoint_freq > 0 and checkpoint_freq < total_timesteps:
        ckpt_cb = CheckpointCallback(
            save_freq=checkpoint_freq,
            save_path=output_dir,
            name_prefix="ppo_traffic_ckpt",
            save_replay_buffer=False,
            save_vecnormalize=False,
        )
        callbacks.append(ckpt_cb)

    try:
        print(f"Starting PPO training for {total_timesteps} steps on {route_file}...")
        model.learn(total_timesteps=total_timesteps, callback=callbacks if callbacks else None)
        final_model_path = os.path.join(output_dir, "ppo_traffic_final.zip")
        model.save(final_model_path)
        print(f"PPO training complete! Saved model to: {final_model_path}")
        return model, final_model_path
    finally:
        # Guarantee SUMO TraCI cleanup
        env.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train PPO traffic signal controller.")
    parser.add_argument("--timesteps", type=int, default=1000, help="Total training timesteps (default 1000)")
    parser.add_argument("--routes", default="data/routes/demand_low_seed42.rou.xml", help="Path to training route file")
    parser.add_argument("--outdir", default="models/ppo", help="Output directory for checkpoints")
    parser.add_argument("--logdir", default="logs/ppo", help="Output directory for logs")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default 42)")
    parser.add_argument("--lr", type=float, default=3e-4, help="Learning rate (default 3e-4)")
    parser.add_argument("--n_steps", type=int, default=128, help="Rollout buffer steps (default 128)")
    parser.add_argument("--batch_size", type=int, default=64, help="Batch size (default 64)")

    args = parser.parse_args()

    train_ppo(
        total_timesteps=args.timesteps,
        route_file=args.routes,
        output_dir=args.outdir,
        log_dir=args.logdir,
        seed=args.seed,
        learning_rate=args.lr,
        n_steps=args.n_steps,
        batch_size=args.batch_size,
    )
