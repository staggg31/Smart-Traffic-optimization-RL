# Traffic-Opt-RL: Code Module Guide

A file-by-file reference for developers and researchers mapping every key module to its responsibility, input parameters, outputs, and dependencies.

---

## 1. Backend & Research Pipeline (`D:\Traffic-Opt-RL\`)

### 1.1 `api/main.py`
- **Responsibility:** FastAPI REST backend providing data endpoints for the research dashboard and handling on-demand SUMO episode execution.
- **Key Functions:**
  - `get_system_status()`: Returns operational state, SUMO v1.28.0, 117 passing tests, checkpoint metadata, and safety constraints.
  - `get_model_metadata()`: Returns hyperparameter JSON for production PPO.
  - `get_training_progress()`: Parses `logs/ppo_production/progress.csv` into step-by-step rollout telemetry.
  - `get_evaluation_scenarios()`: Returns metadata for the 3 held-out scenarios (seeds 301, 302, 303).
  - `get_evaluation_summary(scenario)`: Loads `evaluation_summary.json` containing mean ± std metrics.
  - `get_cross_scenario_comparison()`: Aggregates metrics across all scenarios for tri-controller comparison charts.
  - `run_live_simulation(req)`: Executes real SUMO simulation via TraCI and returns step telemetry records.
- **Error Handling:** Validates scenario IDs, checks checkpoint presence on disk, and wraps TraCI execution in `try ... finally: env.close()`.

### 1.2 `config/schema.py`
- **Responsibility:** Typed dataclass schema enforcing boundary constraints on signal timing and network configuration.
- **Key Class:** `IntersectionConfig`
  - Validates: non-empty lane strings, positive durations, `min_green <= max_green`, finite numbers, non-boolean floats.
  - Used by: all controllers, environment wrappers, evaluation runners, and training pipelines.

### 1.3 `controllers/`
- **`controllers/base.py` (`BaseTrafficController`)**:
  - Abstract base interface defining `act(observation: np.ndarray) -> int` and `reset() -> None`.
  - Ensures controllers emit abstract actions rather than commanding raw SUMO phases directly.
- **`controllers/fixed_time.py` (`FixedTimeController`)**:
  - Cyclic baseline controller holding each green candidate for a predetermined duration (e.g. 42s N-S, 42s E-W).
- **`controllers/actuated.py` (`ActuatedController`)**:
  - Vehicle-actuated controller extending green when queue length exceeds threshold (0.5), switching upon gap-out or max-green (45s).
- **`controllers/ppo.py` (`PPOController`)**:
  - Production wrapper around trained Stable-Baselines3 PPO model. Executes deterministic neural inference.

### 1.4 `environment/`
- **`environment/sumo_environment.py` (`SumoEnvironment`)**:
  - Core simulator wrapper owning TraCI lifecycle. Connects to headless SUMO, coordinates `SignalTransitionManager` for safety, and commands yellow clearance phases.
- **`environment/gym_wrapper.py` (`SumoGymAdapter`)**:
  - Gymnasium-compliant environment adapter exposing `spaces.Box` observation space and `spaces.Discrete` action space for RL libraries.
- **`environment/transition_manager.py` (`SignalTransitionManager`)**:
  - Pure-Python deterministic safety machine enforcing minimum green (5s), yellow clearance (3s), and maximum green (45s).
- **`environment/observation.py` (`ObservationBuilder`)**:
  - Assembles normalized 26-dimensional observation vectors at green decision points. Guards against float32 overflow.
- **`environment/reward.py` (`RewardCalculator`)**:
  - Multi-objective composite reward engine evaluating delay, queues, stops, and emissions.

### 1.5 `evaluation/`
- **`evaluation/runner.py` (`run_simulation_experiment`)**:
  - Controlled evaluation harness recording step records and calculating aggregate metrics (`ExperimentResult`).
- **`evaluation/evaluate_all.py`**:
  - Batch runner evaluating FixedTime, Actuated, and PPO across held-out scenarios and exporting JSON/CSV summaries.
- **`evaluation/benchmark.py`**:
  - Comparative benchmark script evaluating baseline controllers across multiple seeds.

### 1.6 `training/train_ppo.py`
- **Responsibility:** Reproducible training script using Stable-Baselines3 PPO with evaluation callbacks, hyperparameter logging, and model checkpoints.

### 1.7 `scripts/`
- **`scripts/generate_demand.py`**: Reproducible Poisson vehicle route generator respecting valid turn movements.
- **`scripts/run_server.py`**: Standalone runner for FastAPI backend service.

---

## 2. Frontend Subsystem (`frontend/src/`)

### 2.1 Core
- **`App.tsx`**: Main application component orchestrating backend API state, 3D visualizer parameters, and tab views.
- **`types.ts`**: TypeScript type definitions matching FastAPI backend responses, Three.js camera rigs, and scene events.
- **`styles/dashboard.css`**: Light glassmorphic styling system with curated CSS custom properties and responsive layout tokens.

### 2.2 Dashboard Components (`frontend/src/components/`)
- **`DashboardHeader.tsx`**: Header displaying system connectivity, SUMO version, test count, model status, and tab navigation.
- **`SimulationToolbar.tsx`**: Toolbar for scenario switching, controller selection, camera toggles, and speed slider.
- **`SceneViewport.tsx`**: 3D viewport canvas container with status chips and overlay camera controls.
- **`MetricCards.tsx`**: Performance cards displaying `mean ± sample_std` and zero-safe deltas against Fixed-Time. Shows explicit "Unavailable" state for missing metrics.
- **`ControllerComparisonChart.tsx`**: SVG grouped bar chart comparing all 3 controllers across all 3 held-out scenarios.
- **`ComparisonTable.tsx`**: Benchmark matrix displaying tri-controller performance metrics with best-in-class badges.
- **`LiveSimulationPanel.tsx`**: Interactive runner executing real headless SUMO TraCI runs with step scrubber and telemetry table.
- **`TrainingPanel.tsx`**: Convergence charts displaying episode reward, value loss, policy gradient, entropy loss, and hyperparameters.
- **`SafetyPanel.tsx`**: Documents minimum green, yellow clearance, maximum green guardrails, and real-time event logs.
- **`SettingsView.tsx`**: Graphics quality selector (`High`, `Balanced`, `Low`) for GPU optimization.
- **`DashboardFooter.tsx`**: Glassmorphic footer providing research provenance and disclaimers.

### 2.3 3D Scene Engine (`frontend/src/scene/`)
- **`IntersectionScene.tsx`**: R3F Canvas root with WebGL feature detection and error boundary.
- **`CameraRig.tsx`**: Orbit camera with easing transitions (`easeInOut`) between Isometric, Top Down, and Street Level presets.
- **`CityBlocks.tsx`**: Procedural buildings with low-profile foreground limits (6-11m) guaranteeing unobstructed intersection views.
- **`RoadNetwork.tsx`**: Physical roadway, stop bars, crosswalks, curbs, and lane markings.
- **`TrafficSignals.tsx`**: Mast-arm gantries with dynamic emissive red, yellow, and green signal heads.
- **`VehicleFleet.tsx`**: Kinematic vehicle fleet updating positions, wheel rotations, and brake lights in `useFrame`.
- **`VehicleModels.tsx`**: Procedural vehicle meshes (Sedan, SUV, Truck, Bus) with PBR materials.
- **`layout.ts` & `simulation.ts`**: Mathematical layout constants, cubic Bezier turn paths, and procedural car-following kinematics.
- **`materials.ts` & `textures.ts`**: Centralized geometry caches and procedural HTML5 canvas textures (asphalt, paving, facades).
