"""SUMO TraCI environment wrapper with deterministic signal safety.

This module provides a production-grade environment wrapper that owns the simulation
lifecycle through TraCI, enforces safety constraints via SignalTransitionManager,
actively executes legal clearance intervals in SUMO, constructs standardized observation
vectors using ObservationBuilder at valid green decision points, and computes
multi-objective rewards using RewardCalculator.
"""

import math
import os
import sys
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np

from config.schema import IntersectionConfig
from environment.observation import (
    IntersectionMeasurement,
    LaneMeasurement,
    ObservationBuilder,
)
from environment.reward import (
    RawRewardMetrics,
    RewardBreakdown,
    RewardCalculator,
)
from environment.transition_manager import (
    ClearanceStep,
    ManagerState,
    PhaseRequestResult,
    SignalTransitionManager,
)


class SumoEnvironment:
    """Environment wrapper managing SUMO simulation lifecycle and safety guardrails.

    Lifecycle & Design Contracts:
        1. Lifecycle Ownership: Owns launching TraCI on `reset()`, advancing simulation
           step-by-step on `step()`, and gracefully closing TraCI on `close()`.
        2. TraCI Decoupling / Mockability: Accepts an optional `traci_module` dependency,
           enabling 100% mocked unit testing without launching real SUMO binaries.
        3. Topology Decoupling: Takes an explicit `IntersectionConfig` and explicit file
           paths; never hardcodes intersection identifiers or physical capacity limits.
        4. Safety Enforcement & Clearance Execution:
           - Abstract controller actions are mapped through `SignalTransitionManager`.
           - The controller never commands arbitrary phases directly to SUMO.
           - When transitioning between green phases, intermediate clearance phases
             (yellow and all-red) are actively commanded and executed in SUMO for
             their required durations.
           - Observations are constructed ONLY at valid green decision points.
        5. Simulation Clock Synchronization:
           - Discrete control interval defaults to `config.control_interval_seconds`.
           - Elapsed time is measured against SUMO's internal simulation clock, ensuring
             emission integration and transition manager timers are perfectly synchronized.
        6. Return Contract:
           - `reset(seed=...) -> Tuple[np.ndarray, Dict[str, Any]]`
             Returns initial observation vector and informational dictionary.
           - `step(action) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]`
             Returns (observation, scalar_reward, terminated, truncated, info).
    """

    def __init__(
        self,
        config: IntersectionConfig,
        net_file: str,
        route_file: str,
        sumo_cfg_file: Optional[str] = None,
        use_gui: bool = False,
        observation_builder: Optional[ObservationBuilder] = None,
        reward_calculator: Optional[RewardCalculator] = None,
        exit_lanes: Optional[List[str]] = None,
        delta_time: Optional[float] = None,
        max_steps: int = 3600,
        sumo_binary: Optional[str] = None,
        additional_sumo_args: Optional[List[str]] = None,
        traci_module: Optional[Any] = None,
        transition_manager: Optional[SignalTransitionManager] = None,
        clearance_sequences: Optional[Dict[Tuple[int, int], List[ClearanceStep]]] = None,
    ) -> None:
        """Initialize the SUMO environment wrapper.

        Args:
            config: Validated IntersectionConfig.
            net_file: Path to SUMO network XML file.
            route_file: Path to SUMO routes XML file.
            sumo_cfg_file: Optional path to SUMO configuration (.sumocfg) file.
            use_gui: If True, uses sumo-gui instead of headless sumo.
            observation_builder: Optional ObservationBuilder instance. If None,
                creates a default raw builder using config's lanes and green phases.
            reward_calculator: Optional RewardCalculator instance. If None,
                scalar rewards default to 0.0.
            exit_lanes: Optional list of outgoing lane IDs for verified throughput tracking.
            delta_time: Optional control interval override in seconds. Defaults to
                config.control_interval_seconds if None.
            max_steps: Maximum control steps before truncation. Defaults to 3600.
            sumo_binary: Explicit path to sumo/sumo-gui executable. Defaults to SUMO_HOME bin.
            additional_sumo_args: Extra command-line flags passed to SUMO.
            traci_module: Optional injected TraCI module for mocking and testing.
            transition_manager: Optional injected SignalTransitionManager instance.
            clearance_sequences: Optional mapping of `(from_phase, to_phase) -> list[ClearanceStep]`.
                If None, sequences are automatically extracted from SUMO's `tlLogic` on reset.
        """
        if not isinstance(config, IntersectionConfig):
            raise ValueError(f"config must be an IntersectionConfig, got {config!r}.")

        self._config: IntersectionConfig = config
        self._net_file: str = os.path.abspath(net_file)
        self._route_file: str = os.path.abspath(route_file)
        self._sumo_cfg_file: Optional[str] = os.path.abspath(sumo_cfg_file) if sumo_cfg_file else None
        self._use_gui: bool = use_gui

        # Control interval defaults to config.control_interval_seconds
        if delta_time is not None:
            if (
                isinstance(delta_time, bool)
                or not isinstance(delta_time, (int, float))
                or not math.isfinite(delta_time)
                or delta_time <= 0
            ):
                raise ValueError(f"delta_time must be a positive finite number, got {delta_time!r}.")
            self._delta_time: float = float(delta_time)
        else:
            self._delta_time = float(config.control_interval_seconds)

        self._max_steps: int = int(max_steps)
        self._additional_sumo_args: List[str] = list(additional_sumo_args) if additional_sumo_args else []

        # Validate exit lanes (accept explicit override or fallback to config.exit_lanes)
        resolved_exit_lanes = exit_lanes if exit_lanes is not None else getattr(config, "exit_lanes", None)
        if resolved_exit_lanes is not None:
            if not isinstance(resolved_exit_lanes, list) or len(resolved_exit_lanes) == 0:
                raise ValueError("exit_lanes must be a non-empty list of lane IDs.")
            for lane in resolved_exit_lanes:
                if not isinstance(lane, str) or not lane.strip():
                    raise ValueError("All entries in exit_lanes must be non-empty strings.")
            self._exit_lanes: List[str] = list(resolved_exit_lanes)
        else:
            self._exit_lanes = []

        # Observation builder
        if observation_builder is not None:
            if not isinstance(observation_builder, ObservationBuilder):
                raise ValueError("observation_builder must be an ObservationBuilder instance.")
            self._obs_builder: ObservationBuilder = observation_builder
        else:
            self._obs_builder = ObservationBuilder(
                lane_order=config.incoming_lanes,
                green_phase_order=config.green_phase_indices,
                normalizer_config=None,
            )

        # Reward calculator
        self._reward_calc: Optional[RewardCalculator] = reward_calculator

        # Transition manager and clearance configuration
        self._custom_transition_mgr: Optional[SignalTransitionManager] = transition_manager
        self._transition_mgr: SignalTransitionManager = (
            transition_manager if transition_manager is not None else SignalTransitionManager(config=config)
        )
        self._user_clearance_sequences: Optional[Dict[Tuple[int, int], List[ClearanceStep]]] = clearance_sequences
        self._clearance_sequences: Dict[Tuple[int, int], List[ClearanceStep]] = (
            dict(clearance_sequences) if clearance_sequences is not None else {}
        )

        # Injected TraCI module
        self._traci: Any = traci_module
        self._custom_sumo_binary: Optional[str] = sumo_binary

        # Session and vehicle tracking
        self._is_running: bool = False
        self._current_step: int = 0
        self._prev_halted_vehicles: Set[str] = set()
        self._prev_exit_vehicles: Set[str] = set()
        self._approaching_vehicles: Set[str] = set()

    @property
    def is_running(self) -> bool:
        """True if TraCI simulation is actively connected."""
        return self._is_running

    @property
    def current_step(self) -> int:
        """Current control step count in the episode."""
        return self._current_step

    @property
    def config(self) -> IntersectionConfig:
        """Configured intersection configuration."""
        return self._config

    @property
    def obs_builder(self) -> ObservationBuilder:
        """Configured observation builder."""
        return self._obs_builder

    @property
    def delta_time(self) -> float:
        """Control interval in seconds."""
        return self._delta_time

    @property
    def clearance_sequences(self) -> Dict[Tuple[int, int], List[ClearanceStep]]:
        """Active clearance sequences mapping `(from_green, to_green) -> list[ClearanceStep]`."""
        return dict(self._clearance_sequences)


    def _resolve_sumo_binary(self) -> str:
        """Resolve path to SUMO or SUMO-GUI executable."""
        if self._custom_sumo_binary:
            return self._custom_sumo_binary

        sumo_home = os.environ.get("SUMO_HOME")
        if not sumo_home:
            raise EnvironmentError("SUMO_HOME environment variable is not set.")

        binary_name = "sumo-gui.exe" if self._use_gui else "sumo.exe"
        if not sys.platform.startswith("win"):
            binary_name = "sumo-gui" if self._use_gui else "sumo"

        binary_path = os.path.join(sumo_home, "bin", binary_name)
        if not os.path.exists(binary_path):
            raise FileNotFoundError(f"SUMO executable not found at: {binary_path}")

        return binary_path

    def _get_traci(self) -> Any:
        """Get the TraCI module (injected or dynamically imported)."""
        if self._traci is not None:
            return self._traci
        try:
            import traci
            return traci
        except ImportError:
            sumo_home = os.environ.get("SUMO_HOME")
            if sumo_home:
                tools = os.path.join(sumo_home, "tools")
                if tools not in sys.path:
                    sys.path.append(tools)
                import traci
                return traci
            raise


    def _extract_clearance_sequences_from_sumo(self, traci: Any) -> Dict[Tuple[int, int], List[ClearanceStep]]:
        """Extract legal clearance sequences between green phases from SUMO's loaded tlLogic."""
        try:
            logics = traci.trafficlight.getAllProgramLogics(self._config.tls_id)
        except Exception:
            return {}

        if not logics:
            return {}

        active_logic = logics[0]
        phases = active_logic.phases
        num_phases = len(phases)
        green_indices = self._config.green_phase_indices

        extracted: Dict[Tuple[int, int], List[ClearanceStep]] = {}

        for g1 in green_indices:
            for g2 in green_indices:
                if g1 == g2:
                    continue
                steps: List[ClearanceStep] = []
                idx = (g1 + 1) % num_phases
                valid_clearance = True
                while idx != g2:
                    # An intervening phase must not be another green phase
                    if idx in green_indices:
                        valid_clearance = False
                        break
                    p = phases[idx]
                    dur = float(p.duration)
                    if dur > 0:
                        steps.append(ClearanceStep(phase_index=idx, duration_seconds=dur))
                    idx = (idx + 1) % num_phases
                if valid_clearance and len(steps) > 0:
                    extracted[(g1, g2)] = steps

        return extracted

    def reset(self, seed: Optional[int] = None) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Start or restart the SUMO simulation and return the initial observation.

        Args:
            seed: Optional integer random seed passed to SUMO (--seed).

        Returns:
            Tuple[np.ndarray, Dict[str, Any]]: (initial_observation, info_dictionary).

        Raises:
            ValueError: If configured TLS ID or lanes do not exist in the network.
        """
        # Ensure previous connection is cleanly terminated
        self.close()

        traci = self._get_traci()
        binary = self._resolve_sumo_binary()

        # Build SUMO launch command
        cmd = [
            binary,
            "-n", self._net_file,
            "-r", self._route_file,
            "--no-step-log", "true",
            "--quit-on-end", "true",
        ]
        if self._sumo_cfg_file:
            cmd.extend(["-c", self._sumo_cfg_file])
        if seed is not None:
            cmd.extend(["--seed", str(int(seed))])
        cmd.extend(self._additional_sumo_args)

        try:
            traci.start(cmd)
            self._is_running = True

            # Validate traffic light ID exists in network
            available_tls = set(traci.trafficlight.getIDList())
            if self._config.tls_id not in available_tls:
                raise ValueError(
                    f"Configured tls_id '{self._config.tls_id}' not found in network. "
                    f"Available traffic lights: {sorted(available_tls)}."
                )

            # Validate all incoming lanes exist in network
            available_lanes = set(traci.lane.getIDList())
            missing_lanes = [l for l in self._config.incoming_lanes if l not in available_lanes]
            if missing_lanes:
                raise ValueError(
                    f"Configured incoming lanes missing from network: {missing_lanes}."
                )

            # Validate exit lanes exist if supplied
            missing_exit = [l for l in self._exit_lanes if l not in available_lanes]
            if missing_exit:
                raise ValueError(
                    f"Configured exit lanes missing from network: {missing_exit}."
                )

            # Resolve clearance sequences
            if self._user_clearance_sequences is not None:
                self._clearance_sequences = dict(self._user_clearance_sequences)
            else:
                self._clearance_sequences = self._extract_clearance_sequences_from_sumo(traci)

            # Initialize transition manager
            if self._custom_transition_mgr is not None:
                self._transition_mgr = self._custom_transition_mgr
            else:
                self._transition_mgr = SignalTransitionManager(
                    config=self._config,
                    clearance_sequences=self._clearance_sequences if not self._config.clearance_handled_by_sumo else None,
                )

            # Reset state variables
            self._current_step = 0
            self._prev_halted_vehicles = set()
            self._prev_exit_vehicles = set()
            self._approaching_vehicles = set()
            self._transition_mgr.reset(initial_phase=self._config.green_phase_indices[0])

            # Apply initial green phase to SUMO
            traci.trafficlight.setPhase(self._config.tls_id, self._transition_mgr.current_phase)

            # Update initial approaching vehicles
            for lane_id in self._config.incoming_lanes:
                self._approaching_vehicles.update(traci.lane.getLastStepVehicleIDs(lane_id))

            # Collect initial state measurement at green decision point
            measurement = self._collect_intersection_measurement(traci)
            observation = self._obs_builder.build(measurement)

            info = {
                "step": self._current_step,
                "simulation_time": traci.simulation.getTime(),
                "active_green_phase": self._transition_mgr.current_phase,
                "min_green_satisfied": self._transition_mgr.is_min_green_satisfied,
                "expected_vehicles": traci.simulation.getMinExpectedNumber(),
                "throughput_tracking_active": len(self._exit_lanes) > 0,
            }

            return observation, info

        except Exception:
            self.close()
            raise

    def _step_simulation_duration(
        self, traci: Any, duration_seconds: float
    ) -> Tuple[float, float, int, float]:
        """Advance SUMO simulation by duration_seconds, integrating metrics accurately.

        Returns:
            Tuple[float, float, int, float]:
            (actual_elapsed_seconds, total_emissions_mg, new_stops_count, verified_throughput_count).
        """
        if duration_seconds <= 0:
            return 0.0, 0.0, 0, 0.0

        t_start = float(traci.simulation.getTime())
        t_target = t_start + duration_seconds
        step_emissions_mg: float = 0.0
        new_stops_count: int = 0
        verified_throughput_count: float = 0.0

        # Safety loop bound prevents infinite loops on static test mocks
        max_substeps = max(1, int(math.ceil(duration_seconds / 0.01)) + 10)
        substeps_taken = 0

        while substeps_taken < max_substeps:
            t_curr_before = float(traci.simulation.getTime())
            if t_curr_before >= t_target - 1e-6:
                break

            traci.simulationStep()
            substeps_taken += 1
            t_curr_after = float(traci.simulation.getTime())
            substep_dt = max(0.0, t_curr_after - t_curr_before)

            # If mock TraCI does not advance time, step once and break
            if substep_dt == 0.0 and substeps_taken > 0:
                substep_dt = duration_seconds
                t_curr_after = t_target

            # 1. Update approaching vehicles on incoming lanes
            current_incoming_vids: Set[str] = set()
            for lane_id in self._config.incoming_lanes:
                lane_vids = set(traci.lane.getLastStepVehicleIDs(lane_id))
                current_incoming_vids.update(lane_vids)
                self._approaching_vehicles.update(lane_vids)

                # Emissions: rate in mg/s * substep duration in seconds
                co2_rate = float(traci.lane.getCO2Emission(lane_id))
                step_emissions_mg += max(0.0, co2_rate * substep_dt)

            # 2. Track new stops on incoming lanes
            current_halted: Set[str] = set()
            for vid in current_incoming_vids:
                try:
                    if traci.vehicle.getSpeed(vid) < 0.1:
                        current_halted.add(vid)
                except Exception:
                    pass
            new_stops_count += len(current_halted - self._prev_halted_vehicles)
            self._prev_halted_vehicles = current_halted

            # 3. Verified throughput: vehicles appearing on exit lanes that
            # were confirmed to have entered via incoming lanes
            if self._exit_lanes:
                current_exit_vids: Set[str] = set()
                for exit_lane in self._exit_lanes:
                    current_exit_vids.update(traci.lane.getLastStepVehicleIDs(exit_lane))

                new_exit_arrivals = current_exit_vids - self._prev_exit_vehicles
                self._prev_exit_vehicles = current_exit_vids

                # Only count arrivals that were approaching from incoming lanes
                verified_crossings = new_exit_arrivals.intersection(self._approaching_vehicles)
                verified_throughput_count += float(len(verified_crossings))

                # Discard verified crossings from approaching pool
                self._approaching_vehicles.difference_update(verified_crossings)

            if t_curr_after >= t_target - 1e-6:
                break

        actual_elapsed = max(0.0, float(traci.simulation.getTime()) - t_start)
        if actual_elapsed == 0.0 and substeps_taken > 0:
            actual_elapsed = duration_seconds

        return actual_elapsed, step_emissions_mg, new_stops_count, verified_throughput_count

    def step(
        self, action: int
    ) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """Advance the simulation by one control interval using the controller's abstract action.

        Guarantees:
            - Minimum green and allowed transitions are strictly enforced.
            - If a phase change is initiated, intermediate yellow/clearance intervals are
              actively executed in SUMO before the new green is served.
            - Observations are constructed ONLY at valid green decision points.
            - Simulation clocks, transition timers, and emission integration are synchronized.

        Args:
            action: Discrete action index chosen by controller (0 <= action < len(green_phase_indices)).

        Returns:
            Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
            (observation, scalar_reward, terminated, truncated, info).
        """
        if not self._is_running:
            raise RuntimeError("Cannot step environment: simulation is not running. Call reset() first.")

        # Validate action
        num_actions = len(self._config.green_phase_indices)
        if (
            isinstance(action, bool)
            or not isinstance(action, int)
            or action < 0
            or action >= num_actions
        ):
            raise ValueError(
                f"Action {action!r} is out of bounds for discrete action space [0, {num_actions - 1}]."
            )

        traci = self._get_traci()
        target_green_phase = self._config.green_phase_indices[action]
        current_green_phase = self._transition_mgr.current_phase

        # Safety transition manager evaluates request
        request_result = self._transition_mgr.request_phase(target_green_phase)

        step_emissions_mg: float = 0.0
        step_stops_count: int = 0
        step_throughput_count: float = 0.0
        clearance_executed: bool = False
        clearance_duration_seconds: float = 0.0

        # Execute transition logic
        if request_result.accepted and target_green_phase != current_green_phase:
            # Transition accepted: execute clearance sequence before activating new green
            clearance_executed = True
            transition_key = (current_green_phase, target_green_phase)
            clearance_steps = self._clearance_sequences.get(transition_key, [])

            # Active clearance execution in SUMO
            for step in clearance_steps:
                traci.trafficlight.setPhase(self._config.tls_id, step.phase_index)
                c_dt, c_emiss, c_stops, c_thru = self._step_simulation_duration(traci, step.duration_seconds)
                clearance_duration_seconds += c_dt
                step_emissions_mg += c_emiss
                step_stops_count += c_stops
                step_throughput_count += c_thru

                if not self._config.clearance_handled_by_sumo:
                    self._transition_mgr.step(c_dt)

            # Physically activate target green phase in SUMO
            traci.trafficlight.setPhase(self._config.tls_id, target_green_phase)

            if self._config.clearance_handled_by_sumo:
                self._transition_mgr.confirm_phase_change(target_green_phase)

        # Now in the active green phase: advance SUMO for the control interval
        g_dt, g_emiss, g_stops, g_thru = self._step_simulation_duration(traci, self._delta_time)
        step_emissions_mg += g_emiss
        step_stops_count += g_stops
        step_throughput_count += g_thru

        # Advance transition manager timer for the green phase elapsed time
        self._transition_mgr.step(g_dt)
        self._current_step += 1

        # Collect instantaneous queue & waiting time metrics at decision point
        total_waiting_time: float = 0.0
        total_queue: float = 0.0
        for lane_id in self._config.incoming_lanes:
            total_waiting_time += float(traci.lane.getWaitingTime(lane_id))
            total_queue += float(traci.lane.getLastStepHaltingNumber(lane_id))

        raw_metrics = RawRewardMetrics(
            accumulated_waiting_time_seconds=max(0.0, total_waiting_time),
            queue_vehicles=max(0.0, total_queue),
            stops_count=float(max(0, step_stops_count)),
            emissions_total_mg=max(0.0, step_emissions_mg),
            throughput_vehicles=max(0.0, step_throughput_count),
        )

        # Compute multi-objective reward
        if self._reward_calc is not None:
            reward_breakdown = self._reward_calc.calculate(raw_metrics)
            scalar_reward = reward_breakdown.scalar_reward
        else:
            reward_breakdown = None
            scalar_reward = 0.0

        # Construct next observation at valid green decision point
        measurement = self._collect_intersection_measurement(traci)
        observation = self._obs_builder.build(measurement)

        # Determine termination and truncation
        expected_vehicles = traci.simulation.getMinExpectedNumber()
        terminated = expected_vehicles <= 0
        truncated = self._current_step >= self._max_steps

        info = {
            "step": self._current_step,
            "simulation_time": traci.simulation.getTime(),
            "active_green_phase": self._transition_mgr.current_phase,
            "min_green_satisfied": self._transition_mgr.is_min_green_satisfied,
            "is_max_green_exceeded": self._transition_mgr.is_max_green_exceeded,
            "action_accepted": request_result.accepted,
            "action_reason": request_result.reason,
            "clearance_executed": clearance_executed,
            "clearance_duration_seconds": clearance_duration_seconds,
            "clearance_phases": [step.phase_index for step in clearance_steps] if clearance_executed else [],
            "expected_vehicles": expected_vehicles,
            "raw_metrics": raw_metrics,
            "reward_breakdown": reward_breakdown,
            "throughput_tracking_active": len(self._exit_lanes) > 0,
        }

        return observation, scalar_reward, terminated, truncated, info

    def _collect_intersection_measurement(self, traci: Any) -> IntersectionMeasurement:
        """Poll TraCI to construct a validated IntersectionMeasurement snapshot."""
        lane_measurements: Dict[str, LaneMeasurement] = {}

        for lane_id in self._config.incoming_lanes:
            halt_count = float(traci.lane.getLastStepHaltingNumber(lane_id))
            veh_count = float(traci.lane.getLastStepVehicleNumber(lane_id))
            wait_time = float(traci.lane.getWaitingTime(lane_id))
            mean_speed = float(traci.lane.getLastStepMeanSpeed(lane_id))

            lane_measurements[lane_id] = LaneMeasurement(
                queue_length_vehicles=max(0.0, halt_count),
                vehicle_count=max(0.0, veh_count),
                accumulated_waiting_time_seconds=max(0.0, wait_time),
                average_speed_mps=max(0.0, mean_speed),
            )

        return IntersectionMeasurement(
            lane_measurements=lane_measurements,
            current_green_phase=self._transition_mgr.current_phase,
            elapsed_green_seconds=self._transition_mgr.elapsed_green_seconds,
            min_green_satisfied=self._transition_mgr.is_min_green_satisfied,
        )

    def close(self) -> None:
        """Safely close the TraCI connection and shut down the SUMO instance.

        This method is idempotent and exception-safe.
        """
        if self._is_running:
            try:
                traci = self._get_traci()
                traci.close()
            except Exception:
                pass
            finally:
                self._is_running = False

    def __enter__(self) -> "SumoEnvironment":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
