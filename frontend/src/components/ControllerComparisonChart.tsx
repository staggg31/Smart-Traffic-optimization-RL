/**
 * ControllerComparisonChart Component
 *
 * Renders an interactive SVG grouped bar chart comparing all three controllers
 * (Fixed-Time, Actuated, PPO) across all three held-out demand scenarios (Seed 301, 302, 303).
 *
 * Data Lineage:
 * - Loaded from `GET /api/evaluations/comparison`
 * - Directly accesses aggregate results from held-out evaluation summary files
 * - Supports metric switching: Waiting Time, Queue Length, Throughput, Stops, CO2, Reward
 */

import React from 'react';
import { useState } from 'react';
import { ChartColumn, FlaskConical } from 'lucide-react';

interface ComparisonData {
  controllers: string[];
  metrics: string[];
  scenarios: Record<
    string,
    {
      info: { id: string; name: string; vehicle_count: number; seed?: number };
      summary: Record<string, Record<string, { mean: number; sample_std: number }>>;
    }
  >;
}

interface ControllerComparisonChartProps {
  comparisonData: ComparisonData | null;
  selectedController: 'FixedTime' | 'Actuated' | 'PPO';
}

type ChartMetricId = 'waiting' | 'queue' | 'throughput' | 'stops' | 'emissions' | 'reward';

interface MetricTabOption {
  id: ChartMetricId;
  key: string;
  label: string;
  axis: string;
  unit: string;
  scale?: number;
}

const METRIC_TABS: MetricTabOption[] = [
  { id: 'waiting', key: 'mean_waiting_time_seconds', label: 'Waiting Time', axis: 'Waiting Time (s)', unit: 's' },
  { id: 'queue', key: 'mean_queue_vehicles', label: 'Queue Length', axis: 'Queue Length (veh)', unit: 'veh' },
  { id: 'throughput', key: 'total_throughput_vehicles', label: 'Throughput', axis: 'Throughput (veh)', unit: 'veh' },
  { id: 'stops', key: 'total_stops', label: 'Stops', axis: 'Stops (count)', unit: 'stops' },
  { id: 'emissions', key: 'total_emissions_mg', label: 'CO₂ Emissions', axis: 'CO₂ (kg)', unit: 'kg', scale: 0.000001 },
  { id: 'reward', key: 'total_reward', label: 'Reward', axis: 'Reward (pts)', unit: 'pts' },
];

export const CONTROLLER_COLORS: Record<string, string> = {
  FixedTimeController: '#94a3b8',
  ActuatedController: '#fbbf24',
  PPOController: '#10b981',
};

export const CONTROLLER_DISPLAY: Record<string, string> = {
  FixedTimeController: 'Fixed-Time',
  ActuatedController: 'Actuated',
  PPOController: 'PPO (30k Steps)',
};

function niceMax(v: number): number {
  if (v <= 0) return 1;
  const exp = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / exp;
  const step = n <= 1.5 ? 0.25 : n <= 3 ? 0.5 : n <= 7 ? 1 : 2;
  return Math.ceil((v * 1.1) / (step * exp)) * step * exp;
}

export const ControllerComparisonChart: React.FC<ControllerComparisonChartProps> = ({
  comparisonData,
  selectedController,
}) => {
  const [metricId, setMetricId] = useState<ChartMetricId>('waiting');

  if (!comparisonData || !comparisonData.scenarios) {
    return (
      <section className="tod-panel tod-glass">
        <header className="tod-panel-head">
          <h2 className="tod-panel-title">
            <ChartColumn size={17} aria-hidden="true" /> Cross-Scenario Comparison
          </h2>
        </header>
        <div style={{ padding: '24px', textAlign: 'center', color: 'var(--tod-text-3)' }}>
          Loading evaluation database records...
        </div>
      </section>
    );
  }

  const currentTab = METRIC_TABS.find((t) => t.id === metricId) || METRIC_TABS[0];
  const scale = currentTab.scale || 1.0;
  const scenarioKeys = Object.keys(comparisonData.scenarios);
  const controllers = ['FixedTimeController', 'ActuatedController', 'PPOController'];

  // Calculate maximum value across all scenarios and controllers for the selected metric
  let rawMax = 0.1;
  scenarioKeys.forEach((scId) => {
    const sc = comparisonData.scenarios[scId];
    controllers.forEach((c) => {
      const val = (sc.summary[c]?.[currentTab.key]?.mean ?? 0) * scale;
      if (Math.abs(val) > rawMax) rawMax = Math.abs(val);
    });
  });

  const maxVal = niceMax(rawMax);
  const ticks = Array.from({ length: 5 }, (_, i) => (maxVal / 4) * i);

  const W = 580;
  const H = 240;
  const pad = { l: 48, r: 16, t: 18, b: 38 };
  const innerW = W - pad.l - pad.r;
  const innerH = H - pad.t - pad.b;
  const groupW = innerW / (scenarioKeys.length || 1);
  const barW = Math.min(26, (groupW * 0.65) / controllers.length);

  const fmt = (v: number) => (v >= 100 ? Math.round(v).toString() : v.toFixed(1));

  return (
    <section className="tod-panel tod-glass" aria-labelledby="tod-chart-title">
      <header className="tod-panel-head">
        <h2 id="tod-chart-title" className="tod-panel-title">
          <ChartColumn size={17} aria-hidden="true" /> Cross-Scenario Controller Generalization
        </h2>
        <span className="tod-badge tod-badge-green" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
          <FlaskConical size={12} /> Held-Out Evaluation (Seeds 301-303)
        </span>
      </header>

      {/* Metric Selector Tabs */}
      <div className="tod-tabs" role="tablist" aria-label="Comparison metric selector">
        {METRIC_TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={metricId === t.id}
            className="tod-tab"
            onClick={() => setMetricId(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* SVG Bar Chart */}
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="tod-chart"
        role="img"
        aria-label={`${currentTab.axis} by controller across held-out scenarios`}
        style={{ width: '100%', height: 'auto', maxHeight: '260px' }}
      >
        {/* Horizontal Grid Lines & Ticks */}
        {ticks.map((t, idx) => {
          const y = pad.t + innerH - (t / maxVal) * innerH;
          return (
            <g key={`tick-${idx}-${t}`}>
              <line x1={pad.l} x2={W - pad.r} y1={y} y2={y} className="tod-chart-grid" />
              <text x={pad.l - 8} y={y + 3.5} textAnchor="end" className="tod-chart-tick">
                {fmt(t)}
              </text>
            </g>
          );
        })}

        {/* Y Axis Label */}
        <text
          transform={`translate(14, ${pad.t + innerH / 2}) rotate(-90)`}
          textAnchor="middle"
          className="tod-chart-axis"
        >
          {currentTab.axis}
        </text>

        {/* Grouped Bars per Scenario */}
        {scenarioKeys.map((scId, gi) => {
          const sc = comparisonData.scenarios[scId];
          const totalBarsW = barW * controllers.length + 4 * (controllers.length - 1);
          const gx = pad.l + gi * groupW + (groupW - totalBarsW) / 2;

          return (
            <g key={scId}>
              {controllers.map((c, bi) => {
                const val = (sc.summary[c]?.[currentTab.key]?.mean ?? 0) * scale;
                const barH = Math.max(2, (Math.max(0, val) / maxVal) * innerH);
                const bx = gx + bi * (barW + 4);
                const by = pad.t + innerH - barH;

                const isPPO = c === 'PPOController';
                const isSelected =
                  (selectedController === 'FixedTime' && c === 'FixedTimeController') ||
                  (selectedController === 'Actuated' && c === 'ActuatedController') ||
                  (selectedController === 'PPO' && c === 'PPOController');

                return (
                  <g key={c}>
                    <rect
                      x={bx}
                      y={by}
                      width={barW}
                      height={barH}
                      rx={3}
                      fill={CONTROLLER_COLORS[c]}
                      opacity={isSelected ? 1.0 : 0.72}
                      stroke={isSelected ? '#1e293b' : 'none'}
                      strokeWidth={isSelected ? 1.5 : 0}
                    >
                      <title>{`${CONTROLLER_DISPLAY[c]}: ${val.toFixed(2)} ${currentTab.unit}`}</title>
                    </rect>
                    {/* Value label on top of bar */}
                    <text
                      x={bx + barW / 2}
                      y={by - 4}
                      textAnchor="middle"
                      style={{ fontSize: '9px', fill: '#475569', fontWeight: isPPO ? 700 : 500 }}
                    >
                      {val.toFixed(1)}
                    </text>
                  </g>
                );
              })}

              {/* Scenario Label below group */}
              <text
                x={pad.l + gi * groupW + groupW / 2}
                y={H - 12}
                textAnchor="middle"
                className="tod-chart-axis"
                style={{ fontSize: '11px', fontWeight: 600 }}
              >
                {sc.info?.name ? sc.info.name.replace('Held-Out Demand Scenario', 'Scenario') : `Scenario ${gi + 1}`}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Legend */}
      <div style={{ display: 'flex', justifyContent: 'center', gap: '20px', padding: '8px 0 4px', fontSize: '0.75rem' }}>
        {controllers.map((c) => (
          <div key={c} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span
              style={{
                width: '12px',
                height: '12px',
                borderRadius: '3px',
                backgroundColor: CONTROLLER_COLORS[c],
                display: 'inline-block',
              }}
            />
            <span style={{ color: 'var(--tod-text-2)', fontWeight: 500 }}>{CONTROLLER_DISPLAY[c]}</span>
          </div>
        ))}
      </div>
    </section>
  );
};
