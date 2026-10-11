/**
 * TrainingPanel Component
 *
 * Visualizes 234 rollout records of production PPO reinforcement learning training
 * convergence curves sourced from `logs/ppo_production/progress.csv` via `GET /api/training/progress`.
 *
 * Monitored Telemetry:
 * - Mean Episode Reward (-13.5 -> -6.83 convergence progression)
 * - Value Loss (critic MSE error regression)
 * - Policy Gradient Loss (actor policy updates)
 * - Entropy Loss (exploration decay over 30,000 timesteps)
 * - Hyperparameter metadata: learning_rate 3e-4, gamma 0.99, n_steps 128, batch_size 64
 */

import React, { useState } from 'react';
import { Brain, CheckCircle2 } from 'lucide-react';
import type { TrainingProgressPoint } from '../types';

interface TrainingPanelProps {
  progressData: TrainingProgressPoint[];
  metadata?: Record<string, any> | null;
}

export const TrainingPanel: React.FC<TrainingPanelProps> = ({ progressData, metadata: _metadata }) => {
  const [metricKey, setMetricKey] = useState<'ep_rew_mean' | 'value_loss' | 'policy_gradient_loss' | 'entropy_loss'>('ep_rew_mean');

  if (!progressData || progressData.length === 0) {
    return (
      <section className="tod-panel tod-glass">
        <header className="tod-panel-head">
          <h2 className="tod-panel-title">
            <Brain size={18} aria-hidden="true" /> Production PPO Training Telemetry
          </h2>
        </header>
        <div style={{ padding: '36px', textAlign: 'center', color: 'var(--tod-text-3)' }}>
          <span className="tod-dot tod-dot-amber tod-dot-pulse" /> Loading training progress telemetry records...
        </div>
      </section>
    );
  }

  const latest = progressData[progressData.length - 1];

  const values = progressData.map((d) => d[metricKey]);
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const range = maxVal - minVal || 1.0;

  const svgWidth = 840;
  const svgHeight = 240;
  const padding = 28;

  const points = progressData
    .map((d, i) => {
      const x = padding + (i / (progressData.length - 1)) * (svgWidth - 2 * padding);
      const normalizedY = (d[metricKey] - minVal) / range;
      const y = svgHeight - padding - normalizedY * (svgHeight - 2 * padding);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  const metricDescriptions: Record<string, { label: string; desc: string; color: string; fill: string }> = {
    ep_rew_mean: {
      label: 'Mean Episode Rollout Reward',
      desc: 'Progressive convergence of multi-objective reward function (-13.5 → -6.83 pts)',
      color: '#059669',
      fill: 'rgba(5, 150, 105, 0.12)',
    },
    value_loss: {
      label: 'Critic Value Loss',
      desc: 'Mean squared error between value network predictions and rollout returns',
      color: '#2563eb',
      fill: 'rgba(37, 99, 235, 0.12)',
    },
    policy_gradient_loss: {
      label: 'Actor Policy Gradient Loss',
      desc: 'PPO clipped surrogate objective policy loss curve',
      color: '#7c3aed',
      fill: 'rgba(124, 58, 237, 0.12)',
    },
    entropy_loss: {
      label: 'Policy Entropy Exploration',
      desc: 'Controlled exploration decay settling near -0.224 without premature policy collapse',
      color: '#d97706',
      fill: 'rgba(217, 119, 6, 0.12)',
    },
  };

  return (
    <section className="tod-panel tod-glass" aria-labelledby="tod-training-title">
      <header className="tod-panel-head">
        <h2 id="tod-training-title" className="tod-panel-title">
          <Brain size={18} aria-hidden="true" /> Production PPO Training Dynamics Telemetry
        </h2>
        <span className="tod-badge tod-badge-green" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
          <CheckCircle2 size={13} /> 30,000 Timesteps (235 Rollouts)
        </span>
      </header>

      {/* Hyperparameter Summary Grid */}
      <div
        className="tod-safety-grid"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
          gap: '12px',
        }}
      >
        <div className="tod-subcard">
          <span style={{ fontSize: '0.6875rem', color: 'var(--tod-text-3)', textTransform: 'uppercase', fontWeight: 600 }}>Total Timesteps</span>
          <div className="tod-mono" style={{ fontSize: '1.25rem', fontWeight: 700, color: '#0f172a', marginTop: 2 }}>
            30,000
          </div>
          <div style={{ fontSize: '0.6875rem', color: '#059669', fontWeight: 600, marginTop: 2 }}>
            235 iterations
          </div>
        </div>

        <div className="tod-subcard">
          <span style={{ fontSize: '0.6875rem', color: 'var(--tod-text-3)', textTransform: 'uppercase', fontWeight: 600 }}>Learning Rate</span>
          <div className="tod-mono" style={{ fontSize: '1.25rem', fontWeight: 700, color: '#0f172a', marginTop: 2 }}>
            3e-4
          </div>
          <div style={{ fontSize: '0.6875rem', color: '#2563eb', fontWeight: 600, marginTop: 2 }}>
            Adam optimizer
          </div>
        </div>

        <div className="tod-subcard">
          <span style={{ fontSize: '0.6875rem', color: 'var(--tod-text-3)', textTransform: 'uppercase', fontWeight: 600 }}>Batch &amp; Rollout</span>
          <div className="tod-mono" style={{ fontSize: '1.25rem', fontWeight: 700, color: '#0f172a', marginTop: 2 }}>
            64 / 128
          </div>
          <div style={{ fontSize: '0.6875rem', color: 'var(--tod-text-3)', marginTop: 2 }}>
            n_epochs: 10
          </div>
        </div>

        <div className="tod-subcard">
          <span style={{ fontSize: '0.6875rem', color: 'var(--tod-text-3)', textTransform: 'uppercase', fontWeight: 600 }}>Discount &amp; GAE</span>
          <div className="tod-mono" style={{ fontSize: '1.25rem', fontWeight: 700, color: '#0f172a', marginTop: 2 }}>
            γ=0.99
          </div>
          <div style={{ fontSize: '0.6875rem', color: 'var(--tod-text-3)', marginTop: 2 }}>
            GAE-λ: 0.95
          </div>
        </div>

        <div className="tod-subcard">
          <span style={{ fontSize: '0.6875rem', color: 'var(--tod-text-3)', textTransform: 'uppercase', fontWeight: 600 }}>Policy Architecture</span>
          <div className="tod-mono" style={{ fontSize: '1.25rem', fontWeight: 700, color: '#7c3aed', marginTop: 2 }}>
            [64, 64]
          </div>
          <div style={{ fontSize: '0.6875rem', color: '#7c3aed', fontWeight: 600, marginTop: 2 }}>
            MlpPolicy (Dual Head)
          </div>
        </div>

        <div className="tod-subcard">
          <span style={{ fontSize: '0.6875rem', color: 'var(--tod-text-3)', textTransform: 'uppercase', fontWeight: 600 }}>Training Speed</span>
          <div className="tod-mono" style={{ fontSize: '1.25rem', fontWeight: 700, color: '#059669', marginTop: 2 }}>
            {latest.fps.toFixed(0)} FPS
          </div>
          <div style={{ fontSize: '0.6875rem', color: 'var(--tod-text-3)', marginTop: 2 }}>
            Elapsed: {latest.elapsed_time_s.toFixed(0)}s
          </div>
        </div>
      </div>

      {/* Metric Selector Tabs */}
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '10px' }}>
        <p style={{ fontSize: '0.8125rem', color: 'var(--tod-text-2)', margin: 0 }}>
          {metricDescriptions[metricKey].desc}
        </p>

        <div className="tod-tabs" role="tablist" aria-label="Training metric selection">
          {(['ep_rew_mean', 'value_loss', 'policy_gradient_loss', 'entropy_loss'] as const).map((key) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={metricKey === key}
              className="tod-tab"
              onClick={() => setMetricKey(key)}
            >
              {key === 'ep_rew_mean'
                ? 'Mean Reward'
                : key === 'value_loss'
                ? 'Value Loss'
                : key === 'policy_gradient_loss'
                ? 'Policy Loss'
                : 'Entropy Loss'}
            </button>
          ))}
        </div>
      </div>

      {/* SVG Training Convergence Curve */}
      <div
        className="tod-subcard"
        style={{
          background: 'rgba(255, 255, 255, 0.85)',
          padding: '16px',
        }}
      >
        <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} style={{ width: '100%', height: 'auto', display: 'block' }}>
          {/* Grid lines */}
          <line x1={padding} y1={padding} x2={svgWidth - padding} y2={padding} stroke="#e2e8f0" strokeDasharray="3,3" />
          <line x1={padding} y1={svgHeight / 2} x2={svgWidth - padding} y2={svgHeight / 2} stroke="#e2e8f0" strokeDasharray="3,3" />
          <line x1={padding} y1={svgHeight - padding} x2={svgWidth - padding} y2={svgHeight - padding} stroke="#cbd5e1" />

          {/* Area fill */}
          <polygon
            points={`${padding},${svgHeight - padding} ${points} ${svgWidth - padding},${svgHeight - padding}`}
            fill={metricDescriptions[metricKey].fill}
          />

          {/* Curve */}
          <polyline
            fill="none"
            stroke={metricDescriptions[metricKey].color}
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            points={points}
          />

          {/* Y Axis Labels */}
          <text x={padding - 6} y={padding + 4} textAnchor="end" style={{ fontSize: '10px', fill: '#64748b' }}>
            {maxVal >= 10 ? maxVal.toFixed(0) : maxVal.toFixed(2)}
          </text>
          <text x={padding - 6} y={svgHeight / 2 + 4} textAnchor="end" style={{ fontSize: '10px', fill: '#64748b' }}>
            {((maxVal + minVal) / 2).toFixed(2)}
          </text>
          <text x={padding - 6} y={svgHeight - padding + 4} textAnchor="end" style={{ fontSize: '10px', fill: '#64748b' }}>
            {minVal >= 10 ? minVal.toFixed(0) : minVal.toFixed(2)}
          </text>

          {/* X Axis Labels */}
          <text x={padding} y={svgHeight - 8} textAnchor="start" style={{ fontSize: '10px', fill: '#64748b' }}>
            Step 0 (Rollout 0)
          </text>
          <text x={svgWidth / 2} y={svgHeight - 8} textAnchor="middle" style={{ fontSize: '10px', fill: '#64748b' }}>
            Step 15,000 (Rollout 117)
          </text>
          <text x={svgWidth - padding} y={svgHeight - 8} textAnchor="end" style={{ fontSize: '10px', fill: '#64748b' }}>
            Step 30,000 (Rollout 235)
          </text>
        </svg>
      </div>
    </section>
  );
};
