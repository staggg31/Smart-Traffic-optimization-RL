"""Abstract base interface for traffic signal controllers.

This module defines the controller interface for adaptive and baseline signal
control policies.
"""

from abc import ABC, abstractmethod
import numpy as np


class BaseTrafficController(ABC):
    """Abstract base class for all traffic signal controllers.

    This interface decouples the policy's decision-making logic from the underlying
    SUMO/TraCI simulator and safety transition mechanics.

    Action Semantic Note:
        The integer returned by `act(observation)` represents an abstract controller
        action (such as an action index in a discrete action space, e.g. selecting a
        target green-phase candidate or an extend/switch directive).

        Crucially, this return value is NOT a raw SUMO traffic-light phase index or
        a direct TraCI command. The translation from this abstract action into a
        legally executable phase transition—including enforcing minimum green time,
        checking conflict prevention, and executing clearance sequences (yellow / all-red)—
        is strictly the responsibility of the environment and its safety transition layer.
    """

    @abstractmethod
    def act(self, observation: np.ndarray) -> int:
        """Select an abstract controller action given an observation vector.

        Args:
            observation: A numerical array representing the current state of the
                intersection (e.g., normalized queue lengths, waiting times,
                and active phase indicators).

        Returns:
            int: An abstract action index chosen by the policy.
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset internal controller state at the start of a simulation episode."""
        pass
