"""Gymnasium-compatible reinforcement learning environment adapter for SUMO.

This module provides `SumoGymAdapter`, a production-grade `gymnasium.Env` wrapper
around `SumoEnvironment`. It exposes standard Gymnasium spaces, reset/step return
signatures, strict action-space validation, deterministic seeded reproducibility,
and clean lifecycle management without bypassing the underlying transition manager
or safety guardrails.
"""

import math
from typing import Any, Dict, Optional, Tuple
import gymnasium as gym
from gymnasium import spaces
import numpy as np

from config.schema import IntersectionConfig
from environment.observation import ObservationBuilder, ObservationNormalizerConfig
from environment.sumo_environment import SumoEnvironment


class SumoGymAdapter(gym.Env):
    """Gymnasium adapter wrapping SumoEnvironment.

    Architectural & Safety Contract:
        1. Inherits from `gymnasium.Env` and strictly complies with the Gymnasium API:
           - `reset(seed=None, options=None) -> (obs, info)`
           - `step(action) -> (obs, reward, terminated, truncated, info)`
        2. Exposes explicit `action_space` and `observation_space`:
           - `action_space`: `Discrete(P)`, where P is the number of green phase candidates.
           - `observation_space`: `Box(shape=(4L + P + 2,), dtype=np.float32)`.
             If normalized (`is_normalized=True`), bounds are `[0.0, 1.0]`.
             If raw (`is_normalized=False`), lower bound is `0.0` and upper bounds reflect
             physical domain maximums.
        3. All actions pass through the underlying `SignalTransitionManager` via `SumoEnvironment`.
           Intervening yellow clearance phases and minimum green guardrails are strictly enforced.
        4. Closes TraCI resources reliably upon normal exit, exceptions, or `__del__`.
    """

    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 1}

    def __init__(
        self,
        env: SumoEnvironment,
        render_mode: Optional[str] = None,
    ) -> None:
        """Initialize Gymnasium adapter around an existing SumoEnvironment.

        Args:
            env: Active or initialized SumoEnvironment instance.
            render_mode: Optional rendering mode ('human' or 'rgb_array').

        Raises:
            ValueError: If env is not a valid SumoEnvironment instance.
        """
        super().__init__()
        if not isinstance(env, SumoEnvironment):
            raise ValueError(f"env must be a SumoEnvironment instance, got {type(env)!r}.")

        self._env: SumoEnvironment = env
        self.render_mode = render_mode

        config: IntersectionConfig = env.config
        num_lanes = len(config.incoming_lanes)
        num_phases = len(config.green_phase_indices)
        obs_dim = 4 * num_lanes + num_phases + 2

        # 1. Action space: Discrete candidate green phases
        self.action_space: spaces.Discrete = spaces.Discrete(num_phases)

        # 2. Observation space: Bounded according to normalization mode
        self._is_normalized: bool = env.obs_builder.is_normalized

        if self._is_normalized:
            # Normalized features are strictly in [0.0, 1.0]
            self.observation_space: spaces.Box = spaces.Box(
                low=0.0,
                high=1.0,
                shape=(obs_dim,),
                dtype=np.float32,
            )

        else:
            # Physical raw features are non-negative with physical upper bounds
            lows = np.zeros(obs_dim, dtype=np.float32)
            highs = np.full(obs_dim, np.inf, dtype=np.float32)
            # One-hot and min-green flag are bounded by 1.0
            highs[4 * num_lanes : 4 * num_lanes + num_phases] = 1.0
            highs[-1] = 1.0  # min_green_satisfied flag
            self.observation_space = spaces.Box(
                low=lows,
                high=highs,
                shape=(obs_dim,),
                dtype=np.float32,
            )

        self._has_reset: bool = False
        self._is_closed: bool = False

    @property
    def unwrapped_sumo_env(self) -> SumoEnvironment:
        """Access the underlying SumoEnvironment instance."""
        return self._env

    @property
    def is_normalized(self) -> bool:
        """Whether the observation builder uses a normalizer config."""
        return self._is_normalized

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Reset the simulation environment and return initial observation.

        Args:
            seed: Optional integer seed for reproducible SUMO execution.
            options: Optional auxiliary settings dictionary.

        Returns:
            Tuple[np.ndarray, Dict[str, Any]]: Initial observation vector and info dictionary.
        """
        super().reset(seed=seed)
        obs, info = self._env.reset(seed=seed)
        self._has_reset = True
        return obs, info

    def step(
        self, action: int
    ) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """Advance the environment by one control interval with discrete action.

        Args:
            action: Discrete action index (must be in action_space).

        Returns:
            Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
            (observation, reward, terminated, truncated, info).

        Raises:
            RuntimeError: If called before reset() or after close().
            ValueError: If action is out-of-bounds or non-integer.
        """
        if not self._has_reset:
            raise RuntimeError("Cannot step before calling reset().")
        if self._is_closed:
            raise RuntimeError("Cannot step on a closed environment.")

        # Strict action validation
        if not self.action_space.contains(action):
            raise ValueError(
                f"Invalid action {action!r}. Expected discrete integer in range [0, {self.action_space.n - 1}]."
            )

        obs, reward, terminated, truncated, info = self._env.step(int(action))

        # Validate observation conforms to declared space
        if not isinstance(obs, np.ndarray) or obs.dtype != np.float32:
            obs = np.array(obs, dtype=np.float32)

        if not np.all(np.isfinite(obs)):
            raise ValueError("Environment produced non-finite values in observation.")

        return obs, float(reward), bool(terminated), bool(truncated), info

    def render(self) -> Optional[np.ndarray]:
        """Render the environment (if supported by render_mode)."""
        if self.render_mode == "rgb_array":
            # Return dummy array if no GUI snapshot is attached
            return np.zeros((100, 100, 3), dtype=np.uint8)
        return None

    def close(self) -> None:
        """Close simulation resources cleanly."""
        if not self._is_closed:
            self._is_closed = True
            self._env.close()

    def __enter__(self) -> "SumoGymAdapter":
        """Support context manager protocol."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Ensure reliable cleanup on context exit."""
        self.close()

    def __del__(self) -> None:
        """Safety destructor ensuring SUMO process cleanup."""
        try:
            self.close()
        except Exception:
            pass
