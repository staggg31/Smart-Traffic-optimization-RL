"""Unit tests for deterministic signal-transition safety state machine."""

import unittest

from config.schema import IntersectionConfig
from environment.transition_manager import (
    ClearanceStep,
    ManagerState,
    PhaseRequestResult,
    SignalTransitionManager,
)


class TestSignalTransitionManager(unittest.TestCase):
    """Test suite for SignalTransitionManager safety invariants."""

    def setUp(self) -> None:
        """Create a default valid configuration for tests."""
        self.config_sumo_clearance = IntersectionConfig(
            tls_id="J1",
            incoming_lanes=["lane_0", "lane_1"],
            green_phase_indices=[0, 2],
            min_green_seconds=10.0,
            max_green_seconds=30.0,
            control_interval_seconds=1.0,
            clearance_handled_by_sumo=True,
        )

    def test_initial_state_and_properties(self) -> None:
        """Verify initial state after construction and reset."""
        manager = SignalTransitionManager(self.config_sumo_clearance)
        self.assertEqual(manager.current_phase, 0)
        self.assertEqual(manager.elapsed_green_seconds, 0.0)
        self.assertEqual(manager.state, ManagerState.GREEN)
        self.assertFalse(manager.is_min_green_satisfied)
        self.assertFalse(manager.is_max_green_exceeded)
        self.assertFalse(manager.can_transition)
        self.assertIsNone(manager.pending_target_phase)

    def test_elapsed_time_accumulation(self) -> None:
        """Verify deterministic time advancement."""
        manager = SignalTransitionManager(self.config_sumo_clearance)
        manager.step(3.5)
        self.assertEqual(manager.elapsed_green_seconds, 3.5)
        manager.step(6.5)
        self.assertEqual(manager.elapsed_green_seconds, 10.0)
        self.assertTrue(manager.is_min_green_satisfied)
        self.assertTrue(manager.can_transition)
        self.assertFalse(manager.is_max_green_exceeded)

    def test_step_dt_validation(self) -> None:
        """Verify non-finite, boolean, and negative dt values are rejected."""
        manager = SignalTransitionManager(self.config_sumo_clearance)

        with self.assertRaises(ValueError):
            manager.step(-1.0)
        with self.assertRaises(ValueError):
            manager.step(float("nan"))
        with self.assertRaises(ValueError):
            manager.step(float("inf"))
        with self.assertRaises(ValueError):
            manager.step(float("-inf"))
        with self.assertRaises(ValueError):
            manager.step(True)  # type: ignore
        with self.assertRaises(ValueError):
            manager.step("1.0")  # type: ignore

    def test_min_green_rejection_leaves_state_unaltered(self) -> None:
        """Verify phase request rejected before min green does not alter state or timer."""
        manager = SignalTransitionManager(self.config_sumo_clearance)
        manager.step(5.0)  # min_green is 10.0

        result = manager.request_phase(2)
        self.assertFalse(result.accepted)
        self.assertIn("Minimum green not satisfied", result.reason)
        # Verify invariants
        self.assertEqual(manager.current_phase, 0)
        self.assertEqual(manager.elapsed_green_seconds, 5.0)
        self.assertIsNone(manager.pending_target_phase)

    def test_holding_current_phase_accepted_anytime(self) -> None:
        """Verify requesting the current active phase acts as a hold and is accepted."""
        manager = SignalTransitionManager(self.config_sumo_clearance)
        manager.step(3.0)

        result = manager.request_phase(0)
        self.assertTrue(result.accepted)
        self.assertIn("Already in requested phase", result.reason)
        self.assertEqual(manager.current_phase, 0)
        self.assertEqual(manager.elapsed_green_seconds, 3.0)

    def test_invalid_target_phase_rejected_without_state_change(self) -> None:
        """Verify invalid phase targets are safely rejected."""
        manager = SignalTransitionManager(self.config_sumo_clearance)
        manager.step(15.0)

        # Non-configured green phase index
        result = manager.request_phase(99)
        self.assertFalse(result.accepted)
        self.assertEqual(manager.current_phase, 0)
        self.assertEqual(manager.elapsed_green_seconds, 15.0)

        # Boolean target
        result = manager.request_phase(True)  # type: ignore
        self.assertFalse(result.accepted)

    def test_allowed_transitions_enforcement(self) -> None:
        """Verify transitions outside the configured transition graph are rejected."""
        # Allow 0 -> 2, but disallow 2 -> 0
        allowed = {0: [2], 2: []}
        manager = SignalTransitionManager(self.config_sumo_clearance, allowed_transitions=allowed)
        manager.step(10.0)

        # 0 -> 2 is allowed
        result_0_to_2 = manager.request_phase(2)
        self.assertTrue(result_0_to_2.accepted)

        # Confirm switch to 2
        manager.confirm_phase_change(2)
        manager.step(10.0)

        # 2 -> 0 is disallowed
        result_2_to_0 = manager.request_phase(0)
        self.assertFalse(result_2_to_0.accepted)
        self.assertIn("not permitted by transition graph", result_2_to_0.reason)
        self.assertEqual(manager.current_phase, 2)

    def test_max_green_signaling(self) -> None:
        """Verify max green expiration is flagged without breaking safety rules."""
        manager = SignalTransitionManager(self.config_sumo_clearance)
        manager.step(30.0)  # max_green is 30.0
        self.assertTrue(manager.is_max_green_exceeded)

        # Max green does not bypass transition graph
        allowed = {0: []}
        manager_blocked = SignalTransitionManager(self.config_sumo_clearance, allowed_transitions=allowed)
        manager_blocked.step(35.0)
        self.assertTrue(manager_blocked.is_max_green_exceeded)
        res = manager_blocked.request_phase(2)
        self.assertFalse(res.accepted)  # Still blocked by legal transition graph

    def test_sumo_handled_clearance_lifecycle(self) -> None:
        """Verify lifecycle when clearance_handled_by_sumo=True."""
        manager = SignalTransitionManager(self.config_sumo_clearance)
        manager.step(12.0)

        # Request transition to 2
        result = manager.request_phase(2)
        self.assertTrue(result.accepted)
        self.assertEqual(manager.pending_target_phase, 2)
        # Crucial: current_phase is NOT updated until confirmed by simulator
        self.assertEqual(manager.current_phase, 0)
        self.assertFalse(manager.can_transition)

        # Confirm mismatch raises ValueError
        with self.assertRaises(ValueError):
            manager.confirm_phase_change(0)

        # Confirm matching phase
        manager.confirm_phase_change(2)
        self.assertEqual(manager.current_phase, 2)
        self.assertEqual(manager.elapsed_green_seconds, 0.0)
        self.assertIsNone(manager.pending_target_phase)
        self.assertFalse(manager.is_min_green_satisfied)

    def test_externally_managed_clearance_progression(self) -> None:
        """Verify lifecycle when clearance_handled_by_sumo=False with multi-step clearance."""
        config_external = IntersectionConfig(
            tls_id="J1",
            incoming_lanes=["lane_0", "lane_1"],
            green_phase_indices=[0, 2],
            min_green_seconds=10.0,
            max_green_seconds=30.0,
            clearance_handled_by_sumo=False,
        )
        # Explicit clearance sequence from phase 0 to 2:
        # Step 1: Yellow phase (index 1) for 3.0s
        # Step 2: All-red phase (index 9) for 1.0s
        clearance_sequences = {
            (0, 2): [
                ClearanceStep(phase_index=1, duration_seconds=3.0),
                ClearanceStep(phase_index=9, duration_seconds=1.0),
            ]
        }
        manager = SignalTransitionManager(config_external, clearance_sequences=clearance_sequences)
        manager.step(10.0)

        # Request transition
        res = manager.request_phase(2)
        self.assertTrue(res.accepted)
        self.assertEqual(manager.state, ManagerState.CLEARANCE)
        self.assertEqual(manager.current_phase, 1)  # Serving Yellow

        # Advance by 2.0s (still within Yellow)
        manager.step(2.0)
        self.assertEqual(manager.state, ManagerState.CLEARANCE)
        self.assertEqual(manager.current_phase, 1)

        # Advance by 1.5s (finishes Yellow, 0.5s into All-red)
        manager.step(1.5)
        self.assertEqual(manager.state, ManagerState.CLEARANCE)
        self.assertEqual(manager.current_phase, 9)  # Serving All-red

        # Advance by 0.5s (finishes All-red, activates Green Phase 2)
        manager.step(0.5)
        self.assertEqual(manager.state, ManagerState.GREEN)
        self.assertEqual(manager.current_phase, 2)
        self.assertEqual(manager.elapsed_green_seconds, 0.0)

    def test_external_clearance_rejected_if_sequence_undefined(self) -> None:
        """Verify request rejected when clearance sequence is missing."""
        config_external = IntersectionConfig(
            tls_id="J1",
            incoming_lanes=["lane_0", "lane_1"],
            green_phase_indices=[0, 2],
            min_green_seconds=10.0,
            max_green_seconds=30.0,
            clearance_handled_by_sumo=False,
        )
        # Empty clearance sequences mapping
        manager = SignalTransitionManager(config_external, clearance_sequences={})
        manager.step(10.0)

        res = manager.request_phase(2)
        self.assertFalse(res.accepted)
        self.assertIn("no clearance sequence is defined", res.reason)
        self.assertEqual(manager.current_phase, 0)
        self.assertEqual(manager.state, ManagerState.GREEN)

    def test_reset(self) -> None:
        """Verify reset restores initial state and allows specifying initial phase."""
        manager = SignalTransitionManager(self.config_sumo_clearance)
        manager.step(15.0)

        manager.reset(initial_phase=2)
        self.assertEqual(manager.current_phase, 2)
        self.assertEqual(manager.elapsed_green_seconds, 0.0)
        self.assertEqual(manager.state, ManagerState.GREEN)

        with self.assertRaises(ValueError):
            manager.reset(initial_phase=99)


class TestClearanceStep(unittest.TestCase):
    """Test validation of ClearanceStep dataclass."""

    def test_valid_step(self) -> None:
        step = ClearanceStep(phase_index=1, duration_seconds=3.0)
        self.assertEqual(step.phase_index, 1)
        self.assertEqual(step.duration_seconds, 3.0)

    def test_invalid_phase_index(self) -> None:
        with self.assertRaises(ValueError):
            ClearanceStep(phase_index=-1, duration_seconds=3.0)
        with self.assertRaises(ValueError):
            ClearanceStep(phase_index=True, duration_seconds=3.0)  # type: ignore

    def test_invalid_duration(self) -> None:
        with self.assertRaises(ValueError):
            ClearanceStep(phase_index=1, duration_seconds=0.0)
        with self.assertRaises(ValueError):
            ClearanceStep(phase_index=1, duration_seconds=-2.0)
        with self.assertRaises(ValueError):
            ClearanceStep(phase_index=1, duration_seconds=float("nan"))
        with self.assertRaises(ValueError):
            ClearanceStep(phase_index=1, duration_seconds=float("inf"))


if __name__ == "__main__":
    unittest.main()
