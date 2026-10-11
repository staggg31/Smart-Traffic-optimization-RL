import React from 'react';
import { ShieldCheck, Lock, AlertTriangle, Layers, Award, Terminal } from 'lucide-react';
import type { SystemStatus } from '../types';

interface GuardrailsPanelProps {
  status: SystemStatus | null;
}

export const GuardrailsPanel: React.FC<GuardrailsPanelProps> = ({ status }) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Intro Header */}
      <div className="card-premium" style={{ background: 'linear-gradient(to right, #ffffff, #fffbeb)', borderLeft: '4px solid #d97706' }}>
        <div className="card-body" style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ padding: 12, borderRadius: 12, backgroundColor: '#fef3c7', color: '#b45309' }}>
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <h2 style={{ fontSize: '1.125rem', fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
              Architectural Safety Guardrails &amp; Signal State Machine
            </h2>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: 2 }}>
              Rigorous fail-safe constraints preventing dangerous transitions, yellow violations, and approach starvation.
            </p>
          </div>
        </div>
      </div>

      {/* Safety Rules Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16 }}>
        {/* Guardrail 1 */}
        <div className="card-premium card-body" style={{ display: 'flex', flexDirection: 'column', gap: 10, borderTop: '3px solid #059669' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="badge badge-emerald font-mono text-[11px]">RULE #1: UNBREAKABLE</span>
            <Lock className="w-4 h-4 text-emerald-600" />
          </div>
          <h4 style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--text-primary)' }}>Minimum Green Holding Time</h4>
          <div className="font-mono" style={{ fontSize: '1.5rem', fontWeight: 800, color: '#059669' }}>
            {status?.safety_constraints.min_green_seconds.toFixed(1) || '5.0'}s Barrier
          </div>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            The SignalTransitionManager strictly rejects any phase change request before 5.0 seconds of green elapsed time.
            Neither the PPO agent nor baseline controllers can force premature phase termination.
          </p>
        </div>

        {/* Guardrail 2 */}
        <div className="card-premium card-body" style={{ display: 'flex', flexDirection: 'column', gap: 10, borderTop: '3px solid #d97706' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="badge badge-amber font-mono text-[11px]">RULE #2: TRANSITION SAFETY</span>
            <AlertTriangle className="w-4 h-4 text-amber-600" />
          </div>
          <h4 style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--text-primary)' }}>Mandatory Yellow Clearance</h4>
          <div className="font-mono" style={{ fontSize: '1.5rem', fontWeight: 800, color: '#d97706' }}>
            {status?.safety_constraints.yellow_clearance_seconds.toFixed(1) || '3.0'}s Clearance
          </div>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            Green phases never switch instantaneously. Every transition actively executes a 3.0-second intermediate yellow clearance
            phase in SUMO with zero red-light conflicts, allowing stopping distance clearance.
          </p>
        </div>

        {/* Guardrail 3 */}
        <div className="card-premium card-body" style={{ display: 'flex', flexDirection: 'column', gap: 10, borderTop: '3px solid #2563eb' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="badge badge-blue font-mono text-[11px]">RULE #3: FAIRNESS</span>
            <Layers className="w-4 h-4 text-blue-600" />
          </div>
          <h4 style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--text-primary)' }}>Maximum Green Force-Off</h4>
          <div className="font-mono" style={{ fontSize: '1.5rem', fontWeight: 800, color: '#2563eb' }}>
            {status?.safety_constraints.max_green_seconds.toFixed(1) || '45.0'}s Max Bound
          </div>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            Prevents arterial starvation. If a heavy traffic approach holds green continuously, the environment flags
            maximum green expiration at 45.0 seconds, forcing phase alternation to unserved approaches.
          </p>
        </div>
      </div>

      {/* Observation Tensor & Composite Reward Formulation */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 16 }}>
        {/* Observation Tensor Layout */}
        <div className="card-premium">
          <div className="card-header">
            <div className="flex items-center gap-2">
              <Terminal className="w-4 h-4 text-blue-600" />
              <h4 className="card-title">Canonical 36-Dimensional Observation Vector</h4>
            </div>
          </div>
          <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Normalized into <code style={{ color: '#2563eb', fontWeight: 600 }}>[0.0, 1.0]</code> via canonical bounds to ensure stable gradient propagation:
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
              <div style={{ padding: '8px 12px', borderRadius: 8, backgroundColor: '#f8fafc', border: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>[0:8] Approach Queues</span>
                <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>Normalized by 20.0 veh</span>
              </div>
              <div style={{ padding: '8px 12px', borderRadius: 8, backgroundColor: '#f8fafc', border: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>[8:16] Approach Vehicle Counts</span>
                <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>Normalized by 25.0 veh</span>
              </div>
              <div style={{ padding: '8px 12px', borderRadius: 8, backgroundColor: '#f8fafc', border: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>[16:24] Approach Waiting Times</span>
                <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>Normalized by 100.0s</span>
              </div>
              <div style={{ padding: '8px 12px', borderRadius: 8, backgroundColor: '#f8fafc', border: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>[24:32] Mean Approach Speeds</span>
                <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>Normalized by 13.89 m/s (50 km/h)</span>
              </div>
              <div style={{ padding: '8px 12px', borderRadius: 8, backgroundColor: '#f8fafc', border: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>[32:34] Active Phase One-Hot</span>
                <span style={{ color: '#059669', fontWeight: 600 }}>Phase 0 (N-S) or Phase 2 (E-W)</span>
              </div>
              <div style={{ padding: '8px 12px', borderRadius: 8, backgroundColor: '#f8fafc', border: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>[34:36] Timing Status</span>
                <span style={{ color: '#d97706', fontWeight: 600 }}>Elapsed Green (45s max) + Min-Green Barrier</span>
              </div>
            </div>
          </div>
        </div>

        {/* Multi-Objective Composite Reward */}
        <div className="card-premium">
          <div className="card-header">
            <div className="flex items-center gap-2">
              <Award className="w-4 h-4 text-amber-600" />
              <h4 className="card-title">Multi-Objective Composite Reward Objective</h4>
            </div>
          </div>
          <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Formulated as penalized negative cost components plus throughput clearance bonus:
            </p>
            <div style={{ padding: 14, borderRadius: 10, backgroundColor: '#fffbeb', border: '1px solid #fde68a', fontFamily: 'var(--font-mono)', fontSize: '0.8125rem', textAlign: 'center', color: '#b45309', fontWeight: 700 }}>
              r = - ( 1.0·ŵ + 0.5·q̂ + 0.1·ŝ + 0.1·ê ) + 0.5·tp̂
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: 6, borderBottom: '1px solid var(--border-subtle)' }}>
                <span>ŵ (Waiting Time Cost, Weight 1.0):</span>
                <span className="font-mono font-bold">Ref: 100.0 s</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: 6, borderBottom: '1px solid var(--border-subtle)' }}>
                <span>q̂ (Queue Length Cost, Weight 0.5):</span>
                <span className="font-mono font-bold">Ref: 10.0 veh</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: 6, borderBottom: '1px solid var(--border-subtle)' }}>
                <span>ŝ (Vehicle Stops Cost, Weight 0.1):</span>
                <span className="font-mono font-bold">Ref: 5.0 stops</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: 6, borderBottom: '1px solid var(--border-subtle)' }}>
                <span>ê (Tailpipe Emissions Cost, Weight 0.1):</span>
                <span className="font-mono font-bold">Ref: 100,000 mg</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>tp̂ (Completed Throughput Bonus, Weight 0.5):</span>
                <span className="font-mono font-bold text-emerald-600">Ref: 10.0 veh</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
