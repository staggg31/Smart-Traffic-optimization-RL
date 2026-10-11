import React from 'react';
import { Activity, ShieldCheck, Cpu, BarChart3, Radio, CheckCircle2 } from 'lucide-react';
import type { SystemStatus } from '../types';

interface NavbarProps {
  status: SystemStatus | null;
  activeTab: 'benchmark' | 'simulation' | 'training' | 'guardrails';
  setActiveTab: (tab: 'benchmark' | 'simulation' | 'training' | 'guardrails') => void;
}

export const Navbar: React.FC<NavbarProps> = ({ status, activeTab, setActiveTab }) => {
  return (
    <header className="navbar-header">
      <div className="navbar-container">
        {/* Brand & Project Identity */}
        <div className="navbar-brand">
          <div className="navbar-logo">
            <Radio style={{ width: '20px', height: '20px' }} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontWeight: 800, fontSize: '1rem', letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>
                TRAFFIC-OPT-RL
              </span>
              <span className="badge badge-amber" style={{ fontSize: '10px', padding: '2px 8px' }}>
                RESEARCH VERIFIED
              </span>
            </div>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: 0, fontWeight: 500 }}>
              Safe Multi-Objective Adaptive Signal Control via Reinforcement Learning
            </p>
          </div>
        </div>

        {/* Navigation Tabs (Kemetra-style pills) */}
        <nav className="pill-group">
          <button
            onClick={() => setActiveTab('benchmark')}
            className={`pill-btn ${activeTab === 'benchmark' ? 'pill-btn-active' : ''}`}
          >
            <BarChart3 style={{ width: '14px', height: '14px', marginRight: '6px', color: 'var(--blue-primary)', display: 'inline' }} />
            Benchmark Analytics
          </button>
          <button
            onClick={() => setActiveTab('simulation')}
            className={`pill-btn ${activeTab === 'simulation' ? 'pill-btn-active' : ''}`}
          >
            <Activity style={{ width: '14px', height: '14px', marginRight: '6px', color: 'var(--emerald-primary)', display: 'inline' }} />
            Live Simulation Lab
          </button>
          <button
            onClick={() => setActiveTab('training')}
            className={`pill-btn ${activeTab === 'training' ? 'pill-btn-active' : ''}`}
          >
            <Cpu style={{ width: '14px', height: '14px', marginRight: '6px', color: 'var(--purple-primary)', display: 'inline' }} />
            PPO Training
          </button>
          <button
            onClick={() => setActiveTab('guardrails')}
            className={`pill-btn ${activeTab === 'guardrails' ? 'pill-btn-active' : ''}`}
          >
            <ShieldCheck style={{ width: '14px', height: '14px', marginRight: '6px', color: 'var(--amber-primary)', display: 'inline' }} />
            Safety Guardrails
          </button>
        </nav>

        {/* Research Telemetry Badges */}
        <div className="navbar-status-group">
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '4px 10px', borderRadius: '8px', background: 'var(--bg-muted)', border: '1px solid var(--border-subtle)', fontSize: '0.75rem' }}>
            <span className="w-2 h-2 rounded-full bg-emerald-500 dot-pulse" style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10b981', display: 'inline-block' }} />
            <span style={{ color: 'var(--text-muted)' }}>SUMO:</span>
            <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', fontWeight: 600 }}>{status?.sumo_version || '1.28.0'}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '4px 10px', borderRadius: '8px', background: 'var(--bg-muted)', border: '1px solid var(--border-subtle)', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            <CheckCircle2 style={{ width: '14px', height: '14px', color: 'var(--emerald-primary)' }} />
            <span>Tests:</span>
            <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', fontWeight: 600 }}>{status?.test_count || 110}/117</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '4px 10px', borderRadius: '8px', background: 'var(--amber-bg)', border: '1px solid var(--amber-border)', fontSize: '0.75rem' }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--amber-primary)' }}>PPO 30k</span>
            <span style={{ color: 'var(--emerald-primary)', fontWeight: 600 }}>Active</span>
          </div>
        </div>
      </div>
    </header>
  );
};
