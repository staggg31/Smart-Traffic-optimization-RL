/**
 * MetricCards Component
 *
 * Displays authentic performance metrics for the currently selected controller
 * on the active held-out demand scenario.
 *
 * Data Provenance & Scientific Integrity:
 * - Sourced strictly from `GET /api/evaluations/summary?scenario=<id>`
 * - Values represent `mean ± sample_std` across verified held-out evaluation seeds
 * - Deltas are computed directly against the Fixed-Time cyclic baseline:
 *     delta = ((val - baseline) / Math.abs(baseline)) * 100
 * - Explicitly renders "Unavailable" when a metric is missing, null, or not measured
 * - Preserves traffic engineering disclaimers distinguishing lane waiting time from trip delay
 */

import React from 'react';
import {
  Car,
  Clock,
  Layers,
  Octagon,
  Leaf,
  Award,
  ArrowDown,
  ArrowUp,
  Info,
} from 'lucide-react';
import type { ControllerSummary } from '../types';

interface MetricCardsProps {
  /** Summary object for the selected controller from evaluation_summary.json */
  summary: ControllerSummary | null;
  /** Summary object for FixedTimeController, used for computing delta percentages */
  baselineSummary?: ControllerSummary | null;
  /** Active controller name ('FixedTime', 'Actuated', or 'PPO') */
  controllerName: 'FixedTime' | 'Actuated' | 'PPO';
  /** Total vehicle count in the active held-out scenario route file */
  vehicleTotal: number;
}

interface MetricCardDef {
  key: keyof ControllerSummary;
  label: string;
  unit: string;
  higherIsBetter: boolean;
  decimals: number;
  icon: React.FC<{ size?: number; className?: string }>;
  scale?: number;
}

const METRIC_DEFS: MetricCardDef[] = [
  {
    key: 'total_throughput_vehicles',
    label: 'Completed Throughput',
    unit: 'veh',
    higherIsBetter: true,
    decimals: 1,
    icon: Car,
  },
  {
    key: 'mean_waiting_time_seconds',
    label: 'Avg Lane Waiting Time',
    unit: 's',
    higherIsBetter: false,
    decimals: 2,
    icon: Clock,
  },
  {
    key: 'mean_queue_vehicles',
    label: 'Mean Approach Queue',
    unit: 'veh',
    higherIsBetter: false,
    decimals: 2,
    icon: Layers,
  },
  {
    key: 'total_stops',
    label: 'Total Vehicle Stops',
    unit: 'stops',
    higherIsBetter: false,
    decimals: 1,
    icon: Octagon,
  },
  {
    key: 'total_emissions_mg',
    label: 'Total CO₂ Emissions',
    unit: 'kg',
    higherIsBetter: false,
    decimals: 2,
    scale: 0.000001, // convert milligrams to kilograms
    icon: Leaf,
  },
  {
    key: 'total_reward',
    label: 'Multi-Objective Reward',
    unit: 'pts',
    higherIsBetter: true,
    decimals: 2,
    icon: Award,
  },
];

export const MetricCards: React.FC<MetricCardsProps> = ({
  summary,
  baselineSummary,
  controllerName,
  vehicleTotal,
}) => {
  // Loading skeleton while initial API fetch is in flight
  if (!summary) {
    return (
      <section className="tod-metrics" aria-label="Loading performance metrics">
        {METRIC_DEFS.map((def) => (
          <article key={def.key} className="tod-metric tod-glass" style={{ opacity: 0.7 }}>
            <span className="tod-metric-icon" aria-hidden="true">
              <def.icon size={20} />
            </span>
            <div className="tod-metric-body">
              <h3 className="tod-metric-label">{def.label}</h3>
              <p className="tod-metric-value" style={{ fontSize: '1.25rem', color: 'var(--tod-text-3)' }}>
                Fetching API...
              </p>
              <p className="tod-metric-delta tod-metric-delta-ref">Real Held-Out Evaluation</p>
            </div>
          </article>
        ))}
      </section>
    );
  }

  const isBaseline = controllerName === 'FixedTime';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      <section className="tod-metrics" aria-label="Authentic controller performance metrics">
        {METRIC_DEFS.map((def) => {
          const stats = summary[def.key];
          const scale = def.scale || 1.0;

          // Check if metric measurement is available and valid
          const isMeasured = stats?.mean != null && !isNaN(stats.mean);
          const hasStd = stats?.sample_std != null && !isNaN(stats.sample_std);

          const val = isMeasured ? stats.mean! * scale : null;
          const std = hasStd ? stats.sample_std! * scale : null;

          let delta = 0;
          let hasComparison = false;
          let improved = false;

          if (!isBaseline && isMeasured && val !== null && baselineSummary && baselineSummary[def.key]) {
            const baseStats = baselineSummary[def.key];
            if (baseStats?.mean != null && !isNaN(baseStats.mean)) {
              const baseVal = baseStats.mean * scale;
              if (baseVal !== 0) {
                delta = ((val - baseVal) / Math.abs(baseVal)) * 100;
                improved = def.higherIsBetter ? delta > 0 : delta < 0;
                hasComparison = true;
              }
            }
          }

          const Arrow = delta >= 0 ? ArrowUp : ArrowDown;

          return (
            <article key={def.key} className="tod-metric tod-glass">
              <span className="tod-metric-icon" aria-hidden="true">
                <def.icon size={20} />
              </span>
              <div className="tod-metric-body">
                <h3 className="tod-metric-label">{def.label}</h3>

                {isMeasured && val !== null ? (
                  <>
                    <p className="tod-metric-value">
                      {val.toLocaleString('en-US', {
                        minimumFractionDigits: def.decimals,
                        maximumFractionDigits: def.decimals,
                      })}
                      <span className="tod-metric-unit">{def.unit}</span>
                    </p>

                    {/* Statistical uncertainty across seeds */}
                    <div style={{ fontSize: '0.6875rem', color: 'var(--tod-text-3)', marginTop: '-2px' }}>
                      {std !== null ? (
                        <>&plusmn; {std.toFixed(def.decimals)} {def.unit} (held-out seeds)</>
                      ) : (
                        <span>Exact / Deterministic</span>
                      )}
                    </div>
                  </>
                ) : (
                  <>
                    <p className="tod-metric-value" style={{ fontSize: '1.125rem', color: 'var(--tod-text-3)' }}>
                      Unavailable
                    </p>
                    <div style={{ fontSize: '0.6875rem', color: 'var(--tod-text-3)', marginTop: '-2px' }}>
                      Metric not measured
                    </div>
                  </>
                )}

                {/* Percentage comparison against Fixed-Time */}
                {hasComparison ? (
                  <p className={`tod-metric-delta ${improved ? 'tod-good' : 'tod-bad'}`}>
                    <Arrow size={13} aria-hidden="true" />
                    {delta > 0 ? '+' : ''}
                    {delta.toFixed(1)}% <span className="tod-metric-delta-ref">vs. Fixed-Time</span>
                  </p>
                ) : (
                  <p className="tod-metric-delta tod-metric-delta-ref">
                    {isBaseline ? 'Baseline Controller' : (isMeasured ? 'No baseline comparison' : 'Unavailable')}
                  </p>
                )}
              </div>
            </article>
          );
        })}
      </section>

      {/* Traffic Engineering Definition Card */}
      <div
        className="tod-glass"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          padding: '10px 16px',
          fontSize: '0.8125rem',
          color: '#92400e',
          background: 'rgba(254, 243, 199, 0.65)',
          border: '1px solid rgba(251, 191, 36, 0.4)',
          borderRadius: 'var(--tod-radius)',
        }}
      >
        <Info size={17} style={{ flexShrink: 0, color: '#d97706' }} />
        <span>
          <strong>Lane Waiting Time Metric:</strong> Reported waiting time reflects system-wide time-averaged approach delay across 8 incoming lanes
          (accumulated vehicle delay divided by simulation duration in SUMO TraCI), rather than isolated trip travel delay. Evaluated across {vehicleTotal} vehicles in this demand scenario.
        </span>
      </div>
    </div>
  );
};
