"""PPO traffic signal controller implementing the canonical BaseTrafficController interface.

This controller wraps a trained Stable-Baselines3 PPO policy, allowing seamless
integration with evaluation runners and comparative baseline benchmarks.
"""

import os
from typing import Any, Optional
import numpy as np


from controllers.base import BaseTrafficController


class PPOController(BaseTrafficController):
    """PPO-based neural traffic signal controller.

    Safety & Contract:
        1. Emits discrete abstract action indices chosen by the neural policy.
        2. Strictly adheres to BaseTrafficController interface (`act(obs) -> int`, `reset()`).
        3. Never commands TraCI directly; all transitions, minimum-green constraints,
           and yellow clearances remain safely enforced by the environment wrapper.
    """

    def __init__(self, model_path: str, deterministic: bool = True) -> None:
        """Initialize PPOController by loading a trained Stable-Baselines3 model.

        Args:
            model_path: Filepath to the saved SB3 zip checkpoint.
            deterministic: Whether to take deterministic (greedy) mode actions.

        Raises:
            FileNotFoundError: If model_path does not exist.
        """
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"PPO model checkpoint not found at: {model_path}")

        from stable_baselines3 import PPO

        self._model_path = os.path.abspath(model_path)
        self._model = PPO.load(self._model_path)
        self._deterministic = deterministic

    @classmethod
    def from_model(cls, model: Any, deterministic: bool = True) -> "PPOController":
        """Factory method to wrap an in-memory trained SB3 model instance."""
        controller = cls.__new__(cls)
        controller._model_path = "in_memory"
        controller._model = model
        controller._deterministic = deterministic
        return controller

    @property
    def model_path(self) -> str:
        """Path to the loaded checkpoint."""
        return self._model_path

    def act(self, observation: np.ndarray) -> int:
        """Predict abstract action index from observation.

        Args:
            observation: 1D float32 observation vector.

        Returns:
            int: Discrete action index.
        """
        if not isinstance(observation, np.ndarray):
            raise ValueError(f"observation must be a numpy.ndarray, got {type(observation)!r}.")
        if observation.ndim != 1:
            raise ValueError(f"observation must be a 1D array, got shape {observation.shape}.")
        if not np.all(np.isfinite(observation)):
            raise ValueError("observation contains non-finite values (NaN or Inf).")

        action, _states = self._model.predict(observation, deterministic=self._deterministic)
        return int(action)

    def reset(self) -> None:
        """Reset internal recurrent states if applicable (stateless MLP is a no-op)."""
        pass
