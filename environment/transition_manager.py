"""Deterministic signal-transition safety state machine.

This module provides a pure-Python state machine that enforces signal-timing safety
constraints (minimum green duration, maximum green expiration, legal transition graphs,
and optional explicit clearance sequences) independently of SUMO or TraCI.
"""

from dataclasses import dataclass
from enum import Enum
import math
from typing import Dict, List, Optional, Set, Tuple

from config.schema import IntersectionConfig


@dataclass(frozen=True)
class ClearanceStep:
    """Explicit definition of an intermediate clearance phase.

    Attributes:
        phase_index: Abstract phase index served during this clearance step.
        duration_seconds: Duration in seconds to hold this clearance phase.
    """

    phase_index: int
    duration_seconds: float

    def __post_init__(self) -> None:
        if isinstance(self.phase_index, bool) or not isinstance(self.phase_index, int) or self.phase_index < 0:
            raise ValueError(f"phase_index must be a non-negative integer, got {self.phase_index!r}.")
        if (
            isinstance(self.duration_seconds, bool)
            or not isinstance(self.duration_seconds, (int, float))
            or not math.isfinite(self.duration_seconds)
            or self.duration_seconds <= 0
        ):
            raise ValueError(
                f"duration_seconds must be a positive finite number, got {self.duration_seconds!r}."
            )


class ManagerState(Enum):
    """Operational state of the transition manager."""

    GREEN = "GREEN"
    CLEARANCE = "CLEARANCE"


@dataclass(frozen=True)
class PhaseRequestResult:
    """Outcome of a phase transition request.

    Attributes:
        accepted: True if the request was validated and accepted; False if rejected.
        target_phase: The phase requested.
        reason: Explanation of why the request was accepted or rejected.
    """

    accepted: bool
    target_phase: int
    reason: str


class SignalTransitionManager:
    """Deterministic signal-transition manager and safety guardrail.

    Responsibilities & Guarantees:
        1. Minimum Green Enforcement: No transition request away from the active
           green phase is accepted until elapsed green time >= min_green_seconds.
        2. Legal Transitions: Transitions are only permitted between pairs allowed
           by the configured transition graph.
        3. Timer Determinism & State Isolation: A rejected request leaves internal
           state and timers completely unaltered.
        4. Maximum Green Signaling: Flags when max_green_seconds has expired,
           alerting the controller that progression is due without bypassing safety.
        5. Decoupled Physical Execution (clearance_handled_by_sumo=True):
           Accepting an action does NOT claim physical execution has occurred in SUMO.
           Actual execution is confirmed when the environment calls `confirm_phase_change`.
        6. Explicit External Clearance (clearance_handled_by_sumo=False):
           If clearance is managed externally, it requires an explicit mapping of
           `(from_phase, to_phase) -> list[ClearanceStep]` with verified durations,
           making zero assumptions about the number or type of clearance intervals.

    Environment Responsibilities (Out of Scope for Transition Manager):
        - Interfacing with TraCI / SUMO commands (`traci.trafficlight.setPhase`).
        - Polling sensor detectors and constructing observation arrays.
        - Verifying that phase indices match the network's validated `tlLogic`.
    """

    def __init__(
        self,
        config: IntersectionConfig,
        allowed_transitions: Optional[Dict[int, List[int]]] = None,
        clearance_sequences: Optional[Dict[Tuple[int, int], List[ClearanceStep]]] = None,
    ) -> None:
        """Initialize the transition manager.

        Args:
            config: Validated IntersectionConfig instance.
            allowed_transitions: Optional mapping of `from_phase -> [to_phase, ...]`.
                If None, transitions between all configured green phases are permitted.
            clearance_sequences: Optional mapping of `(from_phase, to_phase) -> list[ClearanceStep]`
                defining the exact clearance progression when clearance_handled_by_sumo is False.
        """
        self._config = config
        self._green_phases: Set[int] = set(config.green_phase_indices)

        # Validate allowed transitions
        if allowed_transitions is None:
            self._allowed_transitions: Dict[int, Set[int]] = {
                p: set(self._green_phases) for p in self._green_phases
            }
        else:
            self._allowed_transitions = {}
            for src, targets in allowed_transitions.items():
                if src not in self._green_phases:
                    raise ValueError(f"Source phase {src} in allowed_transitions is not in green_phase_indices.")
                valid_targets = set()
                for tgt in targets:
                    if tgt not in self._green_phases:
                        raise ValueError(f"Target phase {tgt} in allowed_transitions is not in green_phase_indices.")
                    valid_targets.add(tgt)
                self._allowed_transitions[src] = valid_targets

        # Validate clearance sequences when clearance is not handled by SUMO
        self._clearance_sequences: Dict[Tuple[int, int], List[ClearanceStep]] = {}
        if clearance_sequences is not None:
            for (src, tgt), seq in clearance_sequences.items():
                if src not in self._green_phases or tgt not in self._green_phases:
                    raise ValueError(f"Clearance sequence defined for unknown green phase pair ({src}, {tgt}).")
                if not isinstance(seq, list) or len(seq) == 0:
                    raise ValueError(f"Clearance sequence for ({src}, {tgt}) must be a non-empty list of ClearanceStep.")
                for step in seq:
                    if not isinstance(step, ClearanceStep):
                        raise ValueError(f"Invalid clearance step {step!r} for pair ({src}, {tgt}).")
                self._clearance_sequences[(src, tgt)] = list(seq)

        # State tracking
        self._state: ManagerState = ManagerState.GREEN
        self._current_phase: int = config.green_phase_indices[0]
        self._elapsed_green_seconds: float = 0.0
        self._pending_target_phase: Optional[int] = None

        # Clearance progression tracking (used when clearance_handled_by_sumo=False)
        self._active_clearance_sequence: List[ClearanceStep] = []
        self._active_clearance_index: int = 0
        self._clearance_time_remaining: float = 0.0

    @property
    def current_phase(self) -> int:
        """The currently active abstract phase index."""
        return self._current_phase

    @property
    def elapsed_green_seconds(self) -> float:
        """Duration in seconds the current green phase has been continuously active."""
        return self._elapsed_green_seconds

    @property
    def state(self) -> ManagerState:
        """Current operational state (GREEN or CLEARANCE)."""
        return self._state

    @property
    def is_min_green_satisfied(self) -> bool:
        """True if the active green phase has satisfied the minimum green duration."""
        if self._state != ManagerState.GREEN:
            return False
        return self._elapsed_green_seconds >= self._config.min_green_seconds

    @property
    def is_max_green_exceeded(self) -> bool:
        """True if the active green phase has reached or exceeded max_green_seconds."""
        if self._state != ManagerState.GREEN:
            return False
        return self._elapsed_green_seconds >= self._config.max_green_seconds

    @property
    def can_transition(self) -> bool:
        """True if the state machine is eligible to initiate a phase change."""
        return (
            self._state == ManagerState.GREEN
            and self.is_min_green_satisfied
            and self._pending_target_phase is None
        )

    @property
    def pending_target_phase(self) -> Optional[int]:
        """The accepted target phase awaiting simulator confirmation (when SUMO handles clearance)."""
        return self._pending_target_phase

    def reset(self, initial_phase: Optional[int] = None) -> None:
        """Reset internal timers and state to a designated initial green phase.

        Args:
            initial_phase: Optional green phase to start with. If None, defaults
                to the first configured green phase index.
        """
        if initial_phase is None:
            initial_phase = self._config.green_phase_indices[0]
        elif initial_phase not in self._green_phases:
            raise ValueError(f"initial_phase {initial_phase} is not in green_phase_indices.")

        self._state = ManagerState.GREEN
        self._current_phase = initial_phase
        self._elapsed_green_seconds = 0.0
        self._pending_target_phase = None
        self._active_clearance_sequence = []
        self._active_clearance_index = 0
        self._clearance_time_remaining = 0.0

    def step(self, dt: float) -> None:
        """Advance the internal timer by dt seconds.

        Args:
            dt: Discrete time increment in seconds. Must be finite and non-negative.

        Raises:
            ValueError: If dt is not a finite, non-negative real number.
        """
        if (
            isinstance(dt, bool)
            or not isinstance(dt, (int, float))
            or not math.isfinite(dt)
            or dt < 0
        ):
            raise ValueError(f"dt must be a non-negative finite real number, got {dt!r}.")

        if dt == 0.0:
            return

        if self._state == ManagerState.GREEN:
            self._elapsed_green_seconds += float(dt)
        elif self._state == ManagerState.CLEARANCE:
            self._advance_clearance(float(dt))

    def _advance_clearance(self, dt: float) -> None:
        """Advance externally managed clearance progression."""
        remaining_dt = dt
        while remaining_dt > 0 and self._state == ManagerState.CLEARANCE:
            if remaining_dt < self._clearance_time_remaining:
                self._clearance_time_remaining -= remaining_dt
                remaining_dt = 0.0
            else:
                # Step completed
                remaining_dt -= self._clearance_time_remaining
                self._active_clearance_index += 1
                if self._active_clearance_index < len(self._active_clearance_sequence):
                    # Proceed to next clearance step
                    next_step = self._active_clearance_sequence[self._active_clearance_index]
                    self._current_phase = next_step.phase_index
                    self._clearance_time_remaining = next_step.duration_seconds
                else:
                    # Clearance finished: enter target green phase
                    assert self._pending_target_phase is not None
                    self._current_phase = self._pending_target_phase
                    self._state = ManagerState.GREEN
                    self._elapsed_green_seconds = remaining_dt  # carry over any residual dt
                    self._pending_target_phase = None
                    self._active_clearance_sequence = []
                    self._active_clearance_index = 0
                    self._clearance_time_remaining = 0.0
                    remaining_dt = 0.0

    def request_phase(self, target_phase: int) -> PhaseRequestResult:
        """Evaluate a request to transition to target_phase.

        A rejected request does NOT alter the current phase, elapsed time,
        or internal state.

        Args:
            target_phase: The green phase requested.

        Returns:
            PhaseRequestResult indicating acceptance or reason for rejection.
        """
        # Validate target phase type and existence
        if isinstance(target_phase, bool) or not isinstance(target_phase, int) or target_phase not in self._green_phases:
            return PhaseRequestResult(
                accepted=False,
                target_phase=target_phase,
                reason=f"Target phase {target_phase!r} is not a valid configured green phase.",
            )

        # Cannot request transitions while serving an external clearance sequence
        if self._state == ManagerState.CLEARANCE:
            return PhaseRequestResult(
                accepted=False,
                target_phase=target_phase,
                reason="Cannot request phase transition while active clearance sequence is executing.",
            )

        # If already in the requested phase, accept as a hold/continuation
        if target_phase == self._current_phase:
            return PhaseRequestResult(
                accepted=True,
                target_phase=target_phase,
                reason="Already in requested phase. Current green phase held.",
            )

        # If pending confirmation from simulator, reject new requests
        if self._pending_target_phase is not None:
            return PhaseRequestResult(
                accepted=False,
                target_phase=target_phase,
                reason="Prior accepted phase request is still pending execution confirmation.",
            )

        # Check minimum green constraint
        if not self.is_min_green_satisfied:
            return PhaseRequestResult(
                accepted=False,
                target_phase=target_phase,
                reason=(
                    f"Minimum green not satisfied. Elapsed: {self._elapsed_green_seconds:.2f}s, "
                    f"Required: {self._config.min_green_seconds:.2f}s."
                ),
            )

        # Check legal transition graph
        allowed_targets = self._allowed_transitions.get(self._current_phase, set())
        if target_phase not in allowed_targets:
            return PhaseRequestResult(
                accepted=False,
                target_phase=target_phase,
                reason=f"Transition from phase {self._current_phase} to {target_phase} is not permitted by transition graph.",
            )

        # Handle transition based on clearance management mode
        if self._config.clearance_handled_by_sumo:
            # SUMO manages clearance natively in its tlLogic program.
            # We accept the request and record the pending target.
            # We do NOT create artificial clearance states or assume physical execution yet.
            self._pending_target_phase = target_phase
            return PhaseRequestResult(
                accepted=True,
                target_phase=target_phase,
                reason="Transition request accepted. Awaiting confirmation of execution in SUMO.",
            )
        else:
            # Clearance is managed externally by the controller wrapper.
            transition_key = (self._current_phase, target_phase)
            sequence = self._clearance_sequences.get(transition_key)
            if sequence is None:
                return PhaseRequestResult(
                    accepted=False,
                    target_phase=target_phase,
                    reason=(
                        f"External clearance is enabled but no clearance sequence is defined "
                        f"for transition ({self._current_phase} -> {target_phase})."
                    ),
                )

            # Initiate external clearance progression
            self._state = ManagerState.CLEARANCE
            self._pending_target_phase = target_phase
            self._active_clearance_sequence = sequence
            self._active_clearance_index = 0
            self._current_phase = sequence[0].phase_index
            self._clearance_time_remaining = sequence[0].duration_seconds
            self._elapsed_green_seconds = 0.0

            return PhaseRequestResult(
                accepted=True,
                target_phase=target_phase,
                reason="Transition accepted. External clearance sequence initiated.",
            )

    def confirm_phase_change(self, new_phase: int) -> None:
        """Confirm that the simulation has executed the phase transition.

        This method is invoked by the environment when clearance is handled by
        SUMO to verify physical phase activation.

        Args:
            new_phase: The phase now physically active in the simulation.

        Raises:
            ValueError: If new_phase is not an allowed green phase or does not
                match the expected pending target.
        """
        if self._state == ManagerState.CLEARANCE:
            raise ValueError("confirm_phase_change cannot be called during externally managed clearance.")

        if self._pending_target_phase is None:
            raise ValueError("confirm_phase_change called but no phase request was pending.")

        if new_phase != self._pending_target_phase:
            raise ValueError(
                f"Confirmed phase {new_phase} does not match pending target phase {self._pending_target_phase}."
            )

        self._current_phase = new_phase
        self._elapsed_green_seconds = 0.0
        self._pending_target_phase = None
