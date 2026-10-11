/**
 * LiveSimulationPanel Component
 *
 * Provides an interactive UI to trigger and inspect authentic headless SUMO TraCI
 * simulation runs through `POST /api/simulation/run`.
 *
 * Operational Guarantees:
 * - Executes real SUMO simulator binary with deterministic seed
 * - SignalTransitionManager enforces all safety constraints (5s min green, 3s yellow clearance)
 * - Exposes interactive step scrubber with play/pause, step forward, and reset controls
 * - Displays per-step telemetry: waiting time, queue lengths, stops, CO2 emissions, rewards, and active phase
 */

import React, { useState, useEffect } from 'react';
import {
  Play,
  Pause,
  RotateCcw,
  StepForward,
  Activity,
  AlertCircle,
  CheckCircle2,
} from 'lucide-react';
import type { SimulationRunResponse, StepRecord } from '../types';

interface LiveSimulationPanelProps {
  onStepChange?: (step: StepRecord | null) => void;
  selectedScenario: string;
}

export const LiveSimulationPanel: React.FC<LiveSimulationPanelProps> = ({
  onStepChange,
  selectedScenario,
}) => {
  const [controller, setController] = useState<'FixedTime' | 'Actuated' | 'PPO'>('PPO');
  const [maxSteps, setMaxSteps] = useState<number>(120);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [simResult, setSimResult] = useState<SimulationRunResponse | null>(null);
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(150); // ms per step
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleRunSimulation = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    setIsPlaying(false);
    try {
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          controller_type: controller,
          scenario: selectedScenario,
          seed: 301,
          max_steps: maxSteps,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Simulation execution failed.');
      }
      const data: SimulationRunResponse = await res.json();
      setSimResult(data);
      setCurrentStepIndex(0);
      if (data.step_records.length > 0 && onStepChange) {
        onStepChange(data.step_records[0]);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Error communicating with SUMO TraCI runner.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    let interval: any;
    if (isPlaying && simResult && simResult.step_records.length > 0) {
      interval = setInterval(() => {
        setCurrentStepIndex((prev) => {
          if (prev >= simResult.step_records.length - 1) {
            setIsPlaying(false);
            return prev;
          }
          const next = prev + 1;
          if (onStepChange) onStepChange(simResult.step_records[next]);
          return next;
        });
      }, playbackSpeed);
    }
    return () => clearInterval(interval);
  }, [isPlaying, simResult, playbackSpeed, onStepChange]);

  const handleSeek = (index: number) => {
    if (simResult && simResult.step_records[index]) {
      setCurrentStepIndex(index);
      if (onStepChange) onStepChange(simResult.step_records[index]);
    }
  };

  const handleReset = () => {
    setIsPlaying(false);
    setCurrentStepIndex(0);
    if (simResult && simResult.step_records[0] && onStepChange) {
      onStepChange(simResult.step_records[0]);
    }
  };

  const handleStepForward = () => {
    if (simResult && currentStepIndex < simResult.step_records.length - 1) {
      const next = currentStepIndex + 1;
      setCurrentStepIndex(next);
      if (onStepChange) onStepChange(simResult.step_records[next]);
    }
  };

  const currentStep = simResult?.step_records[currentStepIndex] || null;

  return (
    <section className="tod-panel tod-glass" aria-labelledby="tod-traci-title">
      <header className="tod-panel-head">
        <h2 id="tod-traci-title" className="tod-panel-title">
          <Activity size={18} aria-hidden="true" /> Authentic SUMO TraCI Simulation Runner
        </h2>
        <span className="tod-badge tod-badge-green">
          FastAPI Simulation Engine
        </span>
      </header>

      {/* Control Setup & Execution Trigger */}
      <div
        className="tod-subcard"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '14px',
          alignItems: 'end',
        }}
      >
        {/* Controller Type */}
        <div className="tod-field">
          <span className="tod-field-label">Controller Under Test</span>
          <select
            className="tod-select"
            value={controller}
            onChange={(e) => setController(e.target.value as any)}
            disabled={isLoading}
          >
            <option value="FixedTime">Fixed-Time Baseline</option>
            <option value="Actuated">Sensor Actuated</option>
            <option value="PPO">PPO Policy (30,000 steps)</option>
          </select>
        </div>

        {/* Max Steps */}
        <div className="tod-field">
          <span className="tod-field-label">Max Steps (10 - 300)</span>
          <input
            type="number"
            className="tod-select"
            value={maxSteps}
            min={10}
            max={300}
            step={10}
            onChange={(e) => setMaxSteps(Math.max(10, Math.min(300, Number(e.target.value))))}
            disabled={isLoading}
          />
        </div>

        {/* Run Button */}
        <div>
          <button
            type="button"
            className="tod-play-btn"
            style={{
              width: '100%',
              borderRadius: '8px',
              padding: '10px 16px',
              background: isLoading ? 'var(--tod-text-3)' : '#059669',
              color: '#ffffff',
              fontWeight: 700,
              fontSize: '0.8125rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
            }}
            onClick={handleRunSimulation}
            disabled={isLoading}
          >
            {isLoading ? (
              <>
                <span className="tod-spinner" aria-hidden="true" />
                <span>Running SUMO TraCI...</span>
              </>
            ) : (
              <>
                <Play size={16} fill="currentColor" />
                <span>Execute Simulation</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Error Message */}
      {errorMsg && (
        <div
          className="tod-subcard"
          style={{
            background: '#fef2f2',
            border: '1px solid #fecaca',
            color: '#991b1b',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            padding: '10px 16px',
          }}
        >
          <AlertCircle size={18} style={{ color: '#dc2626', flexShrink: 0 }} />
          <span style={{ fontSize: '0.8125rem' }}>{errorMsg}</span>
        </div>
      )}

      {/* TraCI Results & Scrubber */}
      {simResult && simResult.step_records.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {/* Summary Banner */}
          <div
            className="tod-subcard"
            style={{
              background: 'rgba(236, 253, 245, 0.7)',
              border: '1px solid #a7f3d0',
              padding: '12px 16px',
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '12px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#065f46', fontWeight: 600, fontSize: '0.8125rem' }}>
              <CheckCircle2 size={16} style={{ color: '#059669' }} />
              <span>Simulation Run Finished ({simResult.step_records.length} steps simulated)</span>
            </div>
            <div style={{ display: 'flex', gap: '16px', fontSize: '0.75rem', color: '#047857' }} className="tod-mono">
              <span>Avg Waiting: {(simResult.summary.mean_waiting_time_seconds || 0).toFixed(2)}s</span>
              <span>Avg Queue: {(simResult.summary.mean_queue_vehicles || 0).toFixed(2)} veh</span>
              <span>Throughput: {simResult.summary.total_throughput_vehicles || 0} veh</span>
            </div>
          </div>

          {/* Interactive Playback Scrubber */}
          <div className="tod-subcard">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <button
                  type="button"
                  className="tod-ctrl-btn"
                  onClick={() => setIsPlaying(!isPlaying)}
                  title={isPlaying ? 'Pause playback' : 'Play trajectory'}
                >
                  {isPlaying ? <Pause size={16} /> : <Play size={16} fill="currentColor" />}
                </button>
                <button
                  type="button"
                  className="tod-ctrl-btn"
                  onClick={handleStepForward}
                  disabled={isPlaying || currentStepIndex >= simResult.step_records.length - 1}
                  title="Advance 1 step"
                >
                  <StepForward size={16} />
                </button>
                <button
                  type="button"
                  className="tod-ctrl-btn"
                  onClick={handleReset}
                  title="Rewind to step 0"
                >
                  <RotateCcw size={16} />
                </button>
                <span className="tod-mono" style={{ fontSize: '0.8125rem', fontWeight: 700, marginLeft: 6 }}>
                  Step {currentStepIndex + 1} / {simResult.step_records.length} (t = {currentStep?.simulation_time.toFixed(1)}s)
                </span>
              </div>

              {/* Playback Speed */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.75rem' }}>
                <span style={{ color: 'var(--tod-text-3)' }}>Step Interval:</span>
                <select
                  className="tod-select"
                  value={playbackSpeed}
                  onChange={(e) => setPlaybackSpeed(Number(e.target.value))}
                  style={{ padding: '2px 8px', fontSize: '0.75rem' }}
                >
                  <option value={300}>Slow (300ms)</option>
                  <option value={150}>Normal (150ms)</option>
                  <option value={50}>Fast (50ms)</option>
                </select>
              </div>
            </div>

            {/* Range Track */}
            <input
              type="range"
              min={0}
              max={simResult.step_records.length - 1}
              value={currentStepIndex}
              onChange={(e) => handleSeek(Number(e.target.value))}
              className="tod-range"
              style={{
                width: '100%',
                '--tod-range-fill': `${(currentStepIndex / (simResult.step_records.length - 1)) * 100}%`,
              } as React.CSSProperties}
            />
          </div>

          {/* Current Step Telemetry Card */}
          {currentStep && (
            <div
              className="tod-subcard"
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                gap: '12px',
                background: 'rgba(248, 250, 252, 0.8)',
              }}
            >
              <div>
                <span style={{ fontSize: '0.6875rem', color: 'var(--tod-text-3)', textTransform: 'uppercase' }}>Active Phase</span>
                <div className="tod-mono" style={{ fontWeight: 700, fontSize: '1rem', color: '#0f172a' }}>
                  Phase {currentStep.active_green_phase} ({currentStep.active_green_phase === 0 ? 'NS' : 'EW'})
                </div>
              </div>

              <div>
                <span style={{ fontSize: '0.6875rem', color: 'var(--tod-text-3)', textTransform: 'uppercase' }}>Lane Waiting</span>
                <div className="tod-mono" style={{ fontWeight: 700, fontSize: '1rem', color: '#059669' }}>
                  {currentStep.waiting_time_seconds.toFixed(2)} s
                </div>
              </div>

              <div>
                <span style={{ fontSize: '0.6875rem', color: 'var(--tod-text-3)', textTransform: 'uppercase' }}>Approach Queue</span>
                <div className="tod-mono" style={{ fontWeight: 700, fontSize: '1rem', color: '#2563eb' }}>
                  {currentStep.queue_vehicles.toFixed(1)} veh
                </div>
              </div>

              <div>
                <span style={{ fontSize: '0.6875rem', color: 'var(--tod-text-3)', textTransform: 'uppercase' }}>Vehicle Stops</span>
                <div className="tod-mono" style={{ fontWeight: 700, fontSize: '1rem', color: '#d97706' }}>
                  {currentStep.stops}
                </div>
              </div>

              <div>
                <span style={{ fontSize: '0.6875rem', color: 'var(--tod-text-3)', textTransform: 'uppercase' }}>Clearance State</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginTop: '2px' }}>
                  {currentStep.clearance_executed ? (
                    <span className="tod-badge tod-badge-amber" style={{ fontSize: '0.6875rem' }}>
                      Yellow Active ({currentStep.clearance_duration_seconds}s)
                    </span>
                  ) : (
                    <span className="tod-badge tod-badge-green" style={{ fontSize: '0.6875rem' }}>
                      Steady Green
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
};
