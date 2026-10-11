/**
 * App Component
 *
 * Root component orchestrating the Traffic-Opt-RL Research Dashboard:
 *
 * State Architecture & Data Lineage:
 * - Authoritative Backend State:
 *     - `status`: Sourced from `GET /api/status`
 *     - `scenarios`: Sourced from `GET /api/evaluations/scenarios`
 *     - `summaryData`: Sourced from `GET /api/evaluations/summary?scenario=<id>`
 *     - `comparisonData`: Sourced from `GET /api/evaluations/comparison`
 *     - `trainingData`: Sourced from `GET /api/training/progress`
 *     - `modelMeta`: Sourced from `GET /api/model/metadata`
 * - Interactive 3D Scene State:
 *     - `playing`, `speed`, `camera`, `quality`, `stats`, `events`
 * - Navigation Routing:
 *     - 'dashboard': High-viewport 3D centerpiece + authentic metric cards + fast preview
 *     - 'analytics': Cross-scenario comparison chart + tri-controller benchmark matrix
 *     - 'simulation': Authentic SUMO TraCI runner executing real headless simulation episodes
 *     - 'training': 234 rollout records of production PPO learning curves and hyperparameters
 *     - 'safety': Formal guardrails, 26-dim observation space, multi-objective reward formulation
 *     - 'settings': 3D hardware graphics settings (High, Balanced, Low)
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import type {
  SystemStatus,
  ScenarioInfo,
  EvaluationSummaryData,
  TrainingProgressPoint,
  StepRecord,
  CameraPreset,
  CameraCommand,
  CameraCommandType,
  RenderQuality,
  LiveSceneStats,
  SceneEvent,
} from './types';
import { DashboardHeader, type NavTab } from './components/DashboardHeader';
import { SimulationToolbar } from './components/SimulationToolbar';
import { SceneViewport } from './components/SceneViewport';
import { MetricCards } from './components/MetricCards';
import { ControllerComparisonChart } from './components/ControllerComparisonChart';
import { ComparisonTable } from './components/ComparisonTable';
import { LiveSimulationPanel } from './components/LiveSimulationPanel';
import { TrainingPanel } from './components/TrainingPanel';
import { SafetyPanel } from './components/SafetyPanel';
import { SettingsView } from './components/SettingsView';
import { DashboardFooter } from './components/DashboardFooter';
import './styles/dashboard.css';

const MAX_SCENE_EVENTS = 8;

export const App: React.FC = () => {
  // Authoritative API States
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [scenarios, setScenarios] = useState<ScenarioInfo[]>([]);
  const [selectedScenario, setSelectedScenario] = useState<string>('eval_heldout_medium_301');
  const [selectedController, setSelectedController] = useState<'FixedTime' | 'Actuated' | 'PPO'>('PPO');
  const [summaryData, setSummaryData] = useState<EvaluationSummaryData | null>(null);
  const [comparisonData, setComparisonData] = useState<any | null>(null);
  const [trainingData, setTrainingData] = useState<TrainingProgressPoint[]>([]);
  const [modelMeta, setModelMeta] = useState<Record<string, any> | null>(null);
  const [activeTab, setActiveTab] = useState<NavTab>('dashboard');
  const [, setLiveStep] = useState<StepRecord | null>(null);

  // 3D Scene Interactive States
  const [playing, setPlaying] = useState<boolean>(true);
  const [speed, setSpeed] = useState<number>(1.0);
  const [camera, setCamera] = useState<CameraPreset>('isometric');
  const [command, setCommand] = useState<CameraCommand | null>(null);
  const [resetToken, setResetToken] = useState<number>(0);
  const [quality, setQuality] = useState<RenderQuality>('balanced');
  const [stats, setStats] = useState<LiveSceneStats | null>(null);
  const [events, setEvents] = useState<SceneEvent[]>([]);

  // Fetch Initial Authoritative Data from FastAPI Backend
  useEffect(() => {
    async function fetchInitialData() {
      try {
        const [statusRes, scRes, compRes, progRes, metaRes] = await Promise.all([
          fetch('/api/status').then((r) => (r.ok ? r.json() : null)),
          fetch('/api/evaluations/scenarios').then((r) => (r.ok ? r.json() : [])),
          fetch('/api/evaluations/comparison').then((r) => (r.ok ? r.json() : null)),
          fetch('/api/training/progress').then((r) => (r.ok ? r.json() : [])),
          fetch('/api/model/metadata').then((r) => (r.ok ? r.json() : null)),
        ]);
        if (statusRes) setStatus(statusRes);
        if (scRes && scRes.length > 0) setScenarios(scRes);
        if (compRes) setComparisonData(compRes);
        if (progRes) setTrainingData(progRes);
        if (metaRes) setModelMeta(metaRes);
      } catch (err) {
        console.error('Error fetching authoritative API data:', err);
      }
    }
    fetchInitialData();
  }, []);

  // Fetch Scenario Evaluation Summary whenever scenario changes
  useEffect(() => {
    async function fetchScenarioSummary() {
      try {
        const res = await fetch(`/api/evaluations/summary?scenario=${selectedScenario}`);
        if (res.ok) {
          const data = await res.json();
          setSummaryData(data);
        }
      } catch (err) {
        console.error('Error fetching scenario summary:', err);
      }
    }
    fetchScenarioSummary();
  }, [selectedScenario]);

  // Scene Callbacks
  const handleEvent = useCallback((e: SceneEvent) => {
    setEvents((prev) => [e, ...prev].slice(0, MAX_SCENE_EVENTS));
  }, []);

  const resetAnimation = useCallback(() => {
    setResetToken((t) => t + 1);
    setEvents([]);
    setStats(null);
  }, []);

  const sendCommand = useCallback((type: CameraCommandType) => {
    setCommand({ type, nonce: Date.now() });
  }, []);

  // Active scenario details
  const activeScenarioInfo = useMemo(() => {
    return (
      scenarios.find((s) => s.id === selectedScenario) || {
        id: 'eval_heldout_medium_301',
        name: 'Held-Out Scenario 1',
        vehicle_count: 80,
        duration_seconds: 300,
        nominal_flow_vph: 1200,
        route_file: 'eval_medium_seed301.rou.xml',
        seed: 301,
      }
    );
  }, [scenarios, selectedScenario]);

  const currentSummary = useMemo(() => {
    if (!summaryData) return null;
    if (selectedController === 'FixedTime') return summaryData.results.FixedTimeController;
    if (selectedController === 'Actuated') return summaryData.results.ActuatedController;
    return summaryData.results.PPOController;
  }, [summaryData, selectedController]);

  const baselineSummary = useMemo(() => {
    return summaryData?.results?.FixedTimeController || null;
  }, [summaryData]);

  return (
    <div className="tod-root" id="tod-top">
      <div className="tod-shell">
        {/* Top Glassmorphic Navigation & Status Bar */}
        <DashboardHeader
          title="TRAFFIC-OPT-RL"
          subtitle="Simulation-Based Safe Multi-Objective Adaptive Traffic Signal Optimization Using RL"
          status={status}
          active={activeTab}
          onNavigate={setActiveTab}
        />

        {/* Global Scenario & Controller Toolbar (shown on Dashboard and Simulation views) */}
        {(activeTab === 'dashboard' || activeTab === 'simulation') && (
          <SimulationToolbar
            scenarios={scenarios}
            scenarioId={selectedScenario}
            onScenario={setSelectedScenario}
            controller={selectedController}
            onController={setSelectedController}
            playing={playing}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onReset={resetAnimation}
            speed={speed}
            onSpeed={setSpeed}
            camera={camera}
            onCamera={setCamera}
            onOpenLiveSimulation={activeTab !== 'simulation' ? () => setActiveTab('simulation') : undefined}
          />
        )}

        {/* TAB 1: Main Dashboard (3D Centerpiece + Key Metric Cards) */}
        {activeTab === 'dashboard' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {/* 3D Daylight Intersection Centerpiece Viewport */}
            <SceneViewport
              scenario={activeScenarioInfo}
              controller={selectedController}
              constraints={status?.safety_constraints}
              playing={playing}
              speed={speed}
              preset={camera}
              command={command}
              resetToken={resetToken}
              quality={quality}
              onEvent={handleEvent}
              onStats={setStats}
              stats={stats}
              onCommand={sendCommand}
              onTopDown={() => setCamera('top')}
            />

            {/* Performance Metric Cards (placed BELOW the scene to preserve road visibility) */}
            <MetricCards
              summary={currentSummary}
              baselineSummary={baselineSummary}
              controllerName={selectedController}
              vehicleTotal={activeScenarioInfo.vehicle_count}
            />

            {/* Fast Analytics Preview Section */}
            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.2fr) minmax(0, 1fr)', gap: '14px', alignItems: 'start' }}>
              <ControllerComparisonChart
                comparisonData={comparisonData}
                selectedController={selectedController}
              />
              <SafetyPanel
                status={status}
                events={events}
              />
            </div>
          </div>
        )}

        {/* TAB 2: Full Analytics & Cross-Scenario Benchmarks */}
        {activeTab === 'analytics' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <ControllerComparisonChart
              comparisonData={comparisonData}
              selectedController={selectedController}
            />
            <ComparisonTable data={summaryData} />
          </div>
        )}

        {/* TAB 3: Authentic SUMO TraCI Simulation Execution Runner */}
        {activeTab === 'simulation' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <LiveSimulationPanel
              onStepChange={setLiveStep}
              selectedScenario={selectedScenario}
            />
          </div>
        )}

        {/* TAB 4: Production PPO Training Telemetry Convergence */}
        {activeTab === 'training' && (
          <TrainingPanel
            progressData={trainingData}
            metadata={modelMeta}
          />
        )}

        {/* TAB 5: Architectural Signal Safety Guardrails & Observation Space */}
        {activeTab === 'safety' && (
          <SafetyPanel
            status={status}
            events={events}
          />
        )}

        {/* TAB 6: 3D Graphics Settings & Hardware Tuning */}
        {activeTab === 'settings' && (
          <SettingsView
            quality={quality}
            onQuality={setQuality}
          />
        )}

        {/* Glassmorphic Research Footer */}
        <DashboardFooter />
      </div>
    </div>
  );
};

export default App;
