/**
 * SimulationToolbar Component
 *
 * Provides control inputs for:
 * 1. Held-Out Evaluation Scenario selection (Seed 301, 302, 303)
 * 2. Traffic Signal Controller policy selection (Fixed-Time, Actuated, PPO)
 * 3. 3D Visualizer playback (Play/Pause, Reset, Speed 0.25x - 4x)
 * 4. Camera view presets (Isometric, Top Down, Street Level)
 * 5. Direct navigation to authentic SUMO TraCI live simulation runner
 */

import React from 'react';
import {
  Bot,
  ChevronDown,
  Layers,
  Pause,
  Play,
  RotateCcw,
  Video,
  PlayCircle,
} from 'lucide-react';
import type { CameraPreset, ScenarioInfo } from '../types';

export const CAMERAS: { id: CameraPreset; label: string }[] = [
  { id: 'isometric', label: 'Isometric' },
  { id: 'top', label: 'Top Down' },
  { id: 'street', label: 'Street Level' },
];

export const CONTROLLERS_LIST: { id: 'FixedTime' | 'Actuated' | 'PPO'; label: string; short: string }[] = [
  { id: 'FixedTime', label: 'Fixed-Time (Cycle)', short: 'Fixed-Time' },
  { id: 'Actuated', label: 'Actuated (Gap-Out)', short: 'Actuated' },
  { id: 'PPO', label: 'PPO (Reinforcement Learning)', short: 'PPO' },
];

interface SimulationToolbarProps {
  scenarios: ScenarioInfo[];
  scenarioId: string;
  onScenario: (id: string) => void;
  controller: 'FixedTime' | 'Actuated' | 'PPO';
  onController: (id: 'FixedTime' | 'Actuated' | 'PPO') => void;
  playing: boolean;
  onPlay: () => void;
  onPause: () => void;
  onReset: () => void;
  speed: number;
  onSpeed: (v: number) => void;
  camera: CameraPreset;
  onCamera: (c: CameraPreset) => void;
  onOpenLiveSimulation?: () => void;
}

export const SimulationToolbar: React.FC<SimulationToolbarProps> = ({
  scenarios,
  scenarioId,
  onScenario,
  controller,
  onController,
  playing,
  onPlay,
  onPause,
  onReset,
  speed,
  onSpeed,
  camera,
  onCamera,
  onOpenLiveSimulation,
}) => {
  const speedPct = ((speed - 0.25) / (4 - 0.25)) * 100;

  return (
    <section className="tod-toolbar" aria-label="Simulation and view controls">
      {/* Real Scenario Selector */}
      <div className="tod-glass tod-tool tod-tool-select">
        <span className="tod-tool-icon" aria-hidden="true">
          <Layers size={18} />
        </span>
        <label className="tod-field">
          <span className="tod-field-label">Evaluation Scenario</span>
          <span className="tod-select-wrap">
            <select
              className="tod-select"
              value={scenarioId}
              onChange={(e) => onScenario(e.target.value)}
            >
              {scenarios.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.vehicle_count} veh)
                </option>
              ))}
            </select>
            <ChevronDown size={16} className="tod-select-caret" aria-hidden="true" />
          </span>
        </label>
      </div>

      {/* Controller Selector */}
      <div className="tod-glass tod-tool tod-tool-select">
        <span className="tod-tool-icon" aria-hidden="true">
          <Bot size={18} />
        </span>
        <label className="tod-field">
          <span className="tod-field-label">Signal Controller</span>
          <span className="tod-select-wrap">
            <select
              className="tod-select"
              value={controller}
              onChange={(e) => onController(e.target.value as 'FixedTime' | 'Actuated' | 'PPO')}
            >
              {CONTROLLERS_LIST.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>
            <ChevronDown size={16} className="tod-select-caret" aria-hidden="true" />
          </span>
        </label>
      </div>

      {/* 3D Visual Playback Controls */}
      <div className="tod-glass tod-tool tod-playback" role="group" aria-label="3D animation playback">
        <button
          type="button"
          className="tod-play-btn"
          aria-pressed={playing}
          aria-label={playing ? 'Running' : 'Play 3D animation'}
          onClick={onPlay}
        >
          <Play size={18} fill="currentColor" aria-hidden="true" />
        </button>
        <button
          type="button"
          className="tod-ctrl-btn"
          aria-pressed={!playing}
          aria-label="Pause 3D animation"
          onClick={onPause}
        >
          <Pause size={17} aria-hidden="true" />
        </button>
        <button
          type="button"
          className="tod-ctrl-btn"
          aria-label="Reset 3D intersection animation"
          onClick={onReset}
        >
          <RotateCcw size={17} aria-hidden="true" />
        </button>
      </div>

      {/* Animation Speed Slider */}
      <div className="tod-glass tod-tool tod-speed">
        <label className="tod-field tod-field-grow" htmlFor="tod-speed">
          <span className="tod-field-label">3D Scene Speed</span>
          <span className="tod-speed-row">
            <input
              id="tod-speed"
              type="range"
              min={0.25}
              max={4}
              step={0.25}
              value={speed}
              onChange={(e) => onSpeed(Number(e.target.value))}
              className="tod-range"
              style={{ '--tod-range-fill': `${speedPct}%` } as React.CSSProperties}
            />
            <output className="tod-speed-value">{speed.toFixed(speed % 1 === 0 ? 1 : 2)}&times;</output>
          </span>
        </label>
      </div>

      {/* Camera Angle Selector */}
      <div className="tod-glass tod-tool tod-camera">
        <span className="tod-field-label tod-camera-label">
          <Video size={14} aria-hidden="true" /> Camera View
        </span>
        <div className="tod-segmented" role="radiogroup" aria-label="Camera view">
          {CAMERAS.map((c) => (
            <button
              key={c.id}
              type="button"
              role="radio"
              aria-checked={camera === c.id}
              className="tod-segment"
              onClick={() => onCamera(c.id)}
            >
              {c.label}
            </button>
          ))}
        </div>
      </div>

      {/* Authentic TraCI Simulation Jump Button */}
      {onOpenLiveSimulation && (
        <button
          type="button"
          className="tod-glass tod-tool"
          style={{
            cursor: 'pointer',
            border: '1px solid rgba(16, 185, 129, 0.4)',
            background: 'rgba(236, 253, 245, 0.75)',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 16px',
            color: '#065f46',
            fontWeight: 600,
            fontSize: '0.8125rem',
            borderRadius: 'var(--tod-radius)',
          }}
          onClick={onOpenLiveSimulation}
          title="Switch to live SUMO TraCI runner for authentic step telemetry"
        >
          <PlayCircle size={18} style={{ color: '#059669' }} />
          <span>Live SUMO Runner</span>
        </button>
      )}
    </section>
  );
};
