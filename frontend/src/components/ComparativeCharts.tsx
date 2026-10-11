import React, { useState } from 'react';
import { BarChart2 } from 'lucide-react';

interface ComparisonData {
  controllers: string[];
  metrics: string[];
  scenarios: Record<string, {
    info: { id: string; name: string; vehicle_count: number };
    summary: Record<string, Record<string, { mean: number; sample_std: number }>>;
  }>;
}

interface ComparativeChartsProps {
  comparisonData: ComparisonData | null;
}

export const ComparativeCharts: React.FC<ComparativeChartsProps> = ({ comparisonData }) => {
  const [selectedMetric, setSelectedMetric] = useState<string>('mean_waiting_time_seconds');

  if (!comparisonData || !comparisonData.scenarios) {
    return (
      <div className="card-premium card-body text-center" style={{ color: 'var(--text-muted)' }}>
        Loading cross-scenario comparison analytics...
      </div>
    );
  }

  const metricMeta: Record<string, { label: string; unit: string; factor?: number }> = {
    mean_waiting_time_seconds: { label: 'Time-Averaged Waiting Time', unit: 's' },
    mean_queue_vehicles: { label: 'Mean Queue Length', unit: 'veh' },
    total_stops: { label: 'Total Stops', unit: 'stops' },
    total_emissions_mg: { label: 'CO₂ Emissions', unit: 'kg', factor: 0.000001 },
    total_reward: { label: 'Multi-Objective Reward', unit: 'pts' },
  };

  const currentMeta = metricMeta[selectedMetric] || { label: selectedMetric, unit: '' };
  const factor = currentMeta.factor || 1.0;

  const scenarioKeys = Object.keys(comparisonData.scenarios);

  let maxVal = 0.1;
  scenarioKeys.forEach((k) => {
    const sc = comparisonData.scenarios[k];
    ['FixedTimeController', 'ActuatedController', 'PPOController'].forEach((ctrl) => {
      const val = (sc.summary[ctrl]?.[selectedMetric]?.mean || 0) * factor;
      if (Math.abs(val) > maxVal) maxVal = Math.abs(val);
    });
  });
  maxVal = maxVal * 1.15; // 15% headroom

  return (
    <div className="card-premium">
      <div className="card-header">
        <div className="flex items-center gap-2">
          <BarChart2 className="w-4 h-4 text-emerald-600" />
          <h3 className="card-title">
            Cross-Scenario Generalization Comparison
          </h3>
        </div>

        {/* Metric Switcher Pills */}
        <div className="pill-group">
          {Object.entries(metricMeta).map(([k, meta]) => (
            <button
              key={k}
              onClick={() => setSelectedMetric(k)}
              className={`pill-btn ${selectedMetric === k ? 'pill-btn-active' : ''}`}
            >
              {meta.label}
            </button>
          ))}
        </div>
      </div>

      <div className="card-body">
        {/* Bar Chart Visualization */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16 }}>
          {scenarioKeys.map((scKey) => {
            const sc = comparisonData.scenarios[scKey];
            const ft = (sc.summary['FixedTimeController']?.[selectedMetric]?.mean || 0) * factor;
            const ftStd = (sc.summary['FixedTimeController']?.[selectedMetric]?.sample_std || 0) * factor;

            const act = (sc.summary['ActuatedController']?.[selectedMetric]?.mean || 0) * factor;
            const actStd = (sc.summary['ActuatedController']?.[selectedMetric]?.sample_std || 0) * factor;

            const ppo = (sc.summary['PPOController']?.[selectedMetric]?.mean || 0) * factor;
            const ppoStd = (sc.summary['PPOController']?.[selectedMetric]?.sample_std || 0) * factor;

            const getPct = (v: number) => Math.min(100, Math.max(5, (Math.abs(v) / maxVal) * 100));

            return (
              <div
                key={scKey}
                style={{
                  backgroundColor: '#ffffff',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 12,
                  padding: 16,
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  boxShadow: 'var(--shadow-sm)',
                }}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                    <span style={{ fontWeight: 700, fontSize: '0.875rem', color: 'var(--text-primary)' }}>
                      {sc.info.name}
                    </span>
                    <span className="badge badge-amber font-mono">{sc.info.vehicle_count} veh</span>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: 16 }}>
                    Held-out Poisson arrival schedule
                  </div>
                </div>

                {/* Vertical Bar Chart */}
                <div style={{ height: 180, display: 'flex', alignItems: 'flex-end', justifyContent: 'space-around', gap: 16, paddingBottom: 8, borderBottom: '1px solid var(--border-subtle)' }}>
                  {/* Fixed-Time */}
                  <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', height: '100%', justifyContent: 'flex-end' }}>
                    <span style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', fontWeight: 600, color: '#64748b', marginBottom: 4 }}>
                      {ft.toFixed(1)}
                    </span>
                    <div
                      style={{
                        height: `${getPct(ft)}%`,
                        width: '100%',
                        maxWidth: 48,
                        backgroundColor: '#94a3b8',
                        borderRadius: '6px 6px 0 0',
                      }}
                    />
                    <span style={{ fontSize: '0.6875rem', fontWeight: 700, color: '#475569', marginTop: 6 }}>Fixed-Time</span>
                  </div>

                  {/* Actuated */}
                  <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', height: '100%', justifyContent: 'flex-end' }}>
                    <span style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', fontWeight: 600, color: '#2563eb', marginBottom: 4 }}>
                      {act.toFixed(1)}
                    </span>
                    <div
                      style={{
                        height: `${getPct(act)}%`,
                        width: '100%',
                        maxWidth: 48,
                        backgroundColor: '#3b82f6',
                        borderRadius: '6px 6px 0 0',
                      }}
                    />
                    <span style={{ fontSize: '0.6875rem', fontWeight: 700, color: '#2563eb', marginTop: 6 }}>Actuated</span>
                  </div>

                  {/* PPO */}
                  <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', height: '100%', justifyContent: 'flex-end' }}>
                    <span style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', fontWeight: 700, color: '#b45309', marginBottom: 4 }}>
                      {ppo.toFixed(1)}
                    </span>
                    <div
                      style={{
                        height: `${getPct(ppo)}%`,
                        width: '100%',
                        maxWidth: 48,
                        background: 'linear-gradient(to top, #d97706, #f59e0b)',
                        borderRadius: '6px 6px 0 0',
                        boxShadow: '0 2px 8px rgba(217, 119, 6, 0.25)',
                      }}
                    />
                    <span style={{ fontSize: '0.6875rem', fontWeight: 700, color: '#b45309', marginTop: 6 }}>PPO 30k</span>
                  </div>
                </div>

                {/* Numerical Readout */}
                <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 4, textAlign: 'center', fontFamily: 'var(--font-mono)', fontSize: '0.6875rem' }}>
                  <div>
                    <div style={{ color: 'var(--text-subtle)' }}>FT ±std</div>
                    <div style={{ color: 'var(--text-secondary)' }}>±{ftStd.toFixed(1)}</div>
                  </div>
                  <div>
                    <div style={{ color: 'var(--text-subtle)' }}>ACT ±std</div>
                    <div style={{ color: '#2563eb' }}>±{actStd.toFixed(1)}</div>
                  </div>
                  <div>
                    <div style={{ color: 'var(--text-subtle)' }}>PPO ±std</div>
                    <div style={{ color: '#b45309', fontWeight: 700 }}>±{ppoStd.toFixed(1)}</div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Legend */}
        <div style={{ marginTop: 16, display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          <div style={{ display: 'flex', gap: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 10, height: 10, borderRadius: 2, backgroundColor: '#94a3b8' }} />
              <span>Fixed-Time (Cyclic 42s)</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 10, height: 10, borderRadius: 2, backgroundColor: '#3b82f6' }} />
              <span>Actuated (Gap-out & Max-green)</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 10, height: 10, borderRadius: 2, backgroundColor: '#d97706' }} />
              <strong style={{ color: '#0f172a' }}>PPO 30k (Safe Multi-Objective RL)</strong>
            </div>
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6875rem' }}>
            Unit: {currentMeta.unit} (Lower is better for waiting, queues, stops, emissions)
          </div>
        </div>
      </div>
    </div>
  );
};
