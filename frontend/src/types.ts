/**
 * Traffic-Opt-RL Frontend Type Definitions
 *
 * Defines authoritative TypeScript interfaces and contracts matching:
 * 1. FastAPI backend endpoints (/api/status, /api/evaluations/*, /api/training/*, /api/simulation/run)
 * 2. 3D procedural intersection scene engine (camera rigs, vehicle fleet, traffic signals)
 * 3. Glassmorphic dashboard telemetry and analytics state machines
 */

/**
 * System status returned by `GET /api/status`.
 * Reflects backend operational health, SUMO environment specs, test suite count,
 * and authoritative safety constraints enforced by SignalTransitionManager.
 */
export interface SystemStatus {
  status: string;
  title: string;
  python_version: string;
  sumo_version: string;
  test_count: number;
  model: {
    name: string;
    available: boolean;
    path: string;
    size_bytes: number | null;
    has_metadata: boolean;
    has_progress_logs: boolean;
  };
  safety_constraints: {
    min_green_seconds: number;
    yellow_clearance_seconds: number;
    max_green_seconds: number;
    control_interval_seconds: number;
    all_red_seconds: number;
  };
  waiting_metric_explanation: string;
}

/**
 * Held-out demand scenario metadata returned by `GET /api/evaluations/scenarios`.
 */
export interface ScenarioInfo {
  id: string;
  name: string;
  route_file: string;
  seed: number;
  vehicle_count: number;
  duration_seconds: number;
  nominal_flow_vph: number;
}

/**
 * Mean and sample standard deviation statistical bounds for an evaluation metric.
 */
export interface ControllerMetricStats {
  mean: number | null;
  sample_std: number | null;
}

/**
 * Summary of evaluated metrics for a single controller on a held-out scenario.
 * Sourced from `evaluation_summary.json` via `GET /api/evaluations/summary`.
 */
export interface ControllerSummary {
  total_throughput_vehicles?: ControllerMetricStats;
  simulation_time_seconds?: ControllerMetricStats;
  total_steps?: ControllerMetricStats;
  mean_waiting_time_seconds?: ControllerMetricStats;
  mean_queue_vehicles?: ControllerMetricStats;
  total_stops?: ControllerMetricStats;
  total_emissions_mg?: ControllerMetricStats;
  total_reward?: ControllerMetricStats;
  phase_switches?: ControllerMetricStats;
}

/**
 * Complete evaluation summary response for a selected held-out scenario.
 */
export interface EvaluationSummaryData {
  scenario: ScenarioInfo;
  results: {
    FixedTimeController: ControllerSummary;
    ActuatedController: ControllerSummary;
    PPOController: ControllerSummary;
  };
}

/**
 * Raw per-run evaluation record from `GET /api/evaluations/raw`.
 */
export interface RawEvaluationRecord {
  controller_name: string;
  total_steps: number;
  simulation_time_seconds: number;
  total_reward: number;
  mean_waiting_time_seconds: number;
  mean_queue_vehicles: number;
  total_stops: number;
  total_emissions_mg: number;
  total_throughput_vehicles: number;
  throughput_available: boolean;
  terminated: boolean;
  truncated: boolean;
  phase_switches: number;
  clearance_episodes: number;
  seed: number;
  route_file: string;
}

/**
 * Single rollout telemetry point from `progress.csv` via `GET /api/training/progress`.
 */
export interface TrainingProgressPoint {
  timesteps: number;
  iterations: number;
  fps: number;
  elapsed_time_s: number;
  learning_rate: number;
  loss: number;
  value_loss: number;
  policy_gradient_loss: number;
  entropy_loss: number;
  ep_rew_mean: number;
  ep_len_mean: number;
  approx_kl: number;
}

/**
 * Single step telemetry record from real SUMO TraCI execution.
 */
export interface StepRecord {
  step: number;
  simulation_time: number;
  action: number;
  active_green_phase: number;
  reward: number;
  waiting_time_seconds: number;
  queue_vehicles: number;
  stops: number;
  emissions_mg: number;
  throughput: number | null;
  clearance_executed: boolean;
  clearance_duration_seconds: number;
  clearance_phases: number[];
}

/**
 * Response from `POST /api/simulation/run`.
 */
export interface SimulationRunResponse {
  success: boolean;
  controller: string;
  scenario: string;
  seed: number;
  summary: Record<string, any>;
  step_records: StepRecord[];
}

/**
 * Supported controllers in the research dashboard.
 */
export type ControllerId = 'fixed' | 'actuated' | 'ppo';

/**
 * Camera preset perspectives in the 3D scene.
 */
export type CameraPreset = 'isometric' | 'top' | 'street';

/**
 * Camera command types dispatched from toolbar buttons or keyboard shortcuts.
 */
export type CameraCommandType = 'zoomIn' | 'zoomOut' | 'reset' | 'screenshot';

/**
 * Navigation section tab identifier.
 */
export type NavSection = 'dashboard' | 'analytics' | 'simulation' | 'training' | 'safety' | 'settings';

/**
 * Supported metrics in comparison charts.
 */
export type ChartMetric = 'waiting' | 'queue' | 'completed' | 'co2';

/**
 * Three.js rendering quality tiers for GPU performance adaptation.
 */
export type RenderQuality = 'high' | 'balanced' | 'low';

/**
 * Camera animation command with nonce to trigger effect execution.
 */
export interface CameraCommand {
  type: CameraCommandType;
  nonce: number;
}

/**
 * Standardized controller metrics bundle.
 */
export interface ControllerMetrics {
  completed: number;
  waiting: number;
  queue: number;
  travel: number;
  co2: number;
  stops: number;
}

export type MetricKey = keyof ControllerMetrics;

export interface ScenarioDemand {
  ns: number;
  ew: number;
}

export interface Scenario {
  id: string;
  label: string;
  seed: number;
  demand: ScenarioDemand;
}

export interface ControllerInfo {
  id: ControllerId;
  label: string;
  short: string;
}

export interface SafetyConstraints {
  minGreen: number;
  yellow: number;
  allRed: number;
  maxGreen: number;
}

/**
 * Event message emitted during 3D simulation or TraCI execution.
 */
export interface SceneEvent {
  id: number;
  time: string;
  text: string;
  tone: 'phase' | 'vehicle' | 'info' | 'warning';
}

/**
 * Live scene statistics reported by the 3D visualizer animation loop.
 */
export interface LiveSceneStats {
  simTime: string;
  vehicles: number;
  queued: number;
  completed: number;
  phaseLabel: string;
  stage: 'green' | 'yellow' | 'allred';
  violations: number;
}

export type DataSource = 'illustrative' | 'experiment';

export interface ProjectStatus {
  sumoVersion: string;
  tests: { passed: number; total: number };
  ppoModel: 'available' | 'not-connected';
  source: DataSource;
}
