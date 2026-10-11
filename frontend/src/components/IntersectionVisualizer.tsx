import React from 'react';
import { Shield, Clock, AlertTriangle } from 'lucide-react';
import type { StepRecord } from '../types';

interface IntersectionVisualizerProps {
  currentStep?: StepRecord | null;
  activePhase?: number; // 0: NS Green, 1: NS Yellow, 2: EW Green, 3: EW Yellow
  queueNS?: number;
  queueEW?: number;
  waitingTime?: number;
  isSimulating?: boolean;
}

export const IntersectionVisualizer: React.FC<IntersectionVisualizerProps> = ({
  currentStep,
  activePhase = 0,
  queueNS = 0.4,
  queueEW = 0.3,
  waitingTime = 1.0,
  isSimulating = false,
}) => {
  // If currentStep is provided, derive phase and metrics from it
  const phase = currentStep ? currentStep.active_green_phase : activePhase;
  const isYellow = currentStep ? currentStep.clearance_executed : phase === 1 || phase === 3;

  // Phase 0: NS Green, Phase 2: EW Green
  const nsGreen = !isYellow && phase === 0;
  const ewGreen = !isYellow && phase === 2;
  const nsYellow = isYellow && (phase === 0 || phase === 1);
  const ewYellow = isYellow && (phase === 2 || phase === 3);
  const nsRed = !nsGreen && !nsYellow;
  const ewRed = !ewGreen && !ewYellow;

  const simTime = currentStep ? currentStep.simulation_time : 0.0;
  const currentQueue = currentStep ? currentStep.queue_vehicles : (queueNS + queueEW);

  return (
    <div className="card-panel p-5 relative overflow-hidden flex flex-col justify-between">
      {/* Header Info */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-[#1e283d]">
        <div className="flex items-center gap-2.5">
          <div className="w-3 h-3 rounded-full bg-blue-500 animate-pulse" />
          <h3 className="text-sm font-bold text-white tracking-wide uppercase">
            Intersection Topology — Node TLS &quot;C&quot; (4-Leg Dual-Ring)
          </h3>
          <span className="badge badge-blue font-mono text-[11px]">8 Incoming / 8 Exit Lanes</span>
        </div>
        <div className="flex items-center gap-2">
          {isSimulating && (
            <span className="badge badge-yellow animate-pulse font-mono text-xs">
              LIVE TRA-CI RUNNER
            </span>
          )}
          <span className="badge badge-purple font-mono text-xs">
            SumoGymAdapter 36-Dim Obs
          </span>
        </div>
      </div>

      {/* Main Intersection SVG Canvas */}
      <div className="relative my-4 flex items-center justify-center bg-[#07090e] rounded-xl border border-[#1c2538] p-4 min-h-[380px]">
        <svg viewBox="0 0 500 500" className="w-full max-w-[420px] h-auto drop-shadow-2xl">
          {/* Background Asphalt Ground */}
          <rect x="0" y="0" width="500" height="500" fill="#0d111a" rx="16" />

          {/* North-South Roadway */}
          <rect x="180" y="0" width="140" height="500" fill="#182030" />
          {/* East-West Roadway */}
          <rect x="0" y="180" width="500" height="140" fill="#182030" />

          {/* Lane dividers (dashed lines) */}
          {/* North approaches */}
          <line x1="215" y1="0" x2="215" y2="180" stroke="#334155" strokeWidth="2" strokeDasharray="6,6" />
          <line x1="250" y1="0" x2="250" y2="180" stroke="#e2e8f0" strokeWidth="2.5" />
          <line x1="285" y1="0" x2="285" y2="180" stroke="#334155" strokeWidth="2" strokeDasharray="6,6" />

          {/* South approaches */}
          <line x1="215" y1="320" x2="215" y2="500" stroke="#334155" strokeWidth="2" strokeDasharray="6,6" />
          <line x1="250" y1="320" x2="250" y2="500" stroke="#e2e8f0" strokeWidth="2.5" />
          <line x1="285" y1="320" x2="285" y2="500" stroke="#334155" strokeWidth="2" strokeDasharray="6,6" />

          {/* West approaches */}
          <line x1="0" y1="215" x2="180" y2="215" stroke="#334155" strokeWidth="2" strokeDasharray="6,6" />
          <line x1="0" y1="250" x2="180" y2="250" stroke="#e2e8f0" strokeWidth="2.5" />
          <line x1="0" y1="285" x2="180" y2="285" stroke="#334155" strokeWidth="2" strokeDasharray="6,6" />

          {/* East approaches */}
          <line x1="320" y1="215" x2="500" y2="215" stroke="#334155" strokeWidth="2" strokeDasharray="6,6" />
          <line x1="320" y1="250" x2="500" y2="250" stroke="#e2e8f0" strokeWidth="2.5" />
          <line x1="320" y1="285" x2="500" y2="285" stroke="#334155" strokeWidth="2" strokeDasharray="6,6" />

          {/* Intersection Center Box */}
          <rect x="180" y="180" width="140" height="140" fill="#202b40" />

          {/* Crosswalk markings */}
          <line x1="180" y1="176" x2="320" y2="176" stroke="#475569" strokeWidth="4" strokeDasharray="8,8" />
          <line x1="180" y1="324" x2="320" y2="324" stroke="#475569" strokeWidth="4" strokeDasharray="8,8" />
          <line x1="176" y1="180" x2="176" y2="320" stroke="#475569" strokeWidth="4" strokeDasharray="8,8" />
          <line x1="324" y1="180" x2="324" y2="320" stroke="#475569" strokeWidth="4" strokeDasharray="8,8" />

          {/* North Approach Stop Bar & Signal Light Box */}
          <rect x="145" y="145" width="26" height="30" rx="4" fill="#0b0e14" stroke="#334155" strokeWidth="1" />
          <circle cx="158" cy="152" r="4" fill={nsRed ? '#ef4444' : '#3a1114'} className={nsRed ? 'signal-active' : ''} />
          <circle cx="158" cy="160" r="4" fill={nsYellow ? '#f59e0b' : '#3a2b11'} className={nsYellow ? 'signal-active' : ''} />
          <circle cx="158" cy="168" r="4" fill={nsGreen ? '#10b981' : '#113a26'} className={nsGreen ? 'signal-active' : ''} />

          {/* South Approach Signal Box */}
          <rect x="329" y="325" width="26" height="30" rx="4" fill="#0b0e14" stroke="#334155" strokeWidth="1" />
          <circle cx="342" cy="332" r="4" fill={nsRed ? '#ef4444' : '#3a1114'} className={nsRed ? 'signal-active' : ''} />
          <circle cx="342" cy="340" r="4" fill={nsYellow ? '#f59e0b' : '#3a2b11'} className={nsYellow ? 'signal-active' : ''} />
          <circle cx="342" cy="348" r="4" fill={nsGreen ? '#10b981' : '#113a26'} className={nsGreen ? 'signal-active' : ''} />

          {/* East Approach Signal Box */}
          <rect x="325" y="145" width="30" height="26" rx="4" fill="#0b0e14" stroke="#334155" strokeWidth="1" />
          <circle cx="332" cy="158" r="4" fill={ewRed ? '#ef4444' : '#3a1114'} className={ewRed ? 'signal-active' : ''} />
          <circle cx="340" cy="158" r="4" fill={ewYellow ? '#f59e0b' : '#3a2b11'} className={ewYellow ? 'signal-active' : ''} />
          <circle cx="348" cy="158" r="4" fill={ewGreen ? '#10b981' : '#113a26'} className={ewGreen ? 'signal-active' : ''} />

          {/* West Approach Signal Box */}
          <rect x="145" y="329" width="30" height="26" rx="4" fill="#0b0e14" stroke="#334155" strokeWidth="1" />
          <circle cx="152" cy="342" r="4" fill={ewRed ? '#ef4444' : '#3a1114'} className={ewRed ? 'signal-active' : ''} />
          <circle cx="160" cy="342" r="4" fill={ewYellow ? '#f59e0b' : '#3a2b11'} className={ewYellow ? 'signal-active' : ''} />
          <circle cx="168" cy="342" r="4" fill={ewGreen ? '#10b981' : '#113a26'} className={ewGreen ? 'signal-active' : ''} />

          {/* Approach Labels */}
          <text x="250" y="30" fill="#94a3b8" fontSize="11" fontWeight="700" textAnchor="middle" letterSpacing="2">NORTH (N_in_0,1)</text>
          <text x="250" y="485" fill="#94a3b8" fontSize="11" fontWeight="700" textAnchor="middle" letterSpacing="2">SOUTH (S_in_0,1)</text>
          <text x="15" y="254" fill="#94a3b8" fontSize="11" fontWeight="700" textAnchor="start" letterSpacing="2">WEST (W_in)</text>
          <text x="485" y="254" fill="#94a3b8" fontSize="11" fontWeight="700" textAnchor="end" letterSpacing="2">EAST (E_in)</text>

          {/* Queue Bars / Representation */}
          {/* North Queue indicator */}
          <rect x="255" y="70" width="22" height={Math.min(95, Math.max(10, queueNS * 28))} rx="3" fill="#3b82f6" opacity="0.8" />
          <text x="266" y="62" fill="#60a5fa" fontSize="9" fontWeight="bold" textAnchor="middle" className="font-mono">Q: {queueNS.toFixed(1)}</text>

          {/* South Queue indicator */}
          <rect x="222" y={330 + Math.max(0, 95 - Math.min(95, queueNS * 28))} width="22" height={Math.min(95, Math.max(10, queueNS * 28))} rx="3" fill="#3b82f6" opacity="0.8" />

          {/* East Queue indicator */}
          <rect x="330" y="222" width={Math.min(95, Math.max(10, queueEW * 28))} height="22" rx="3" fill="#8b5cf6" opacity="0.8" />
          <text x="435" y="215" fill="#a78bfa" fontSize="9" fontWeight="bold" textAnchor="end" className="font-mono">Q: {queueEW.toFixed(1)}</text>

          {/* West Queue indicator */}
          <rect x={70 + Math.max(0, 95 - Math.min(95, queueEW * 28))} y="255" width={Math.min(95, Math.max(10, queueEW * 28))} height="22" rx="3" fill="#8b5cf6" opacity="0.8" />

          {/* Flow Direction Arrows */}
          {nsGreen && (
            <g stroke="#10b981" strokeWidth="3" fill="none">
              <path d="M 270 120 L 270 200 M 264 190 L 270 200 L 276 190" className="animate-pulse" />
              <path d="M 230 380 L 230 300 M 224 310 L 230 300 L 236 310" className="animate-pulse" />
            </g>
          )}
          {ewGreen && (
            <g stroke="#10b981" strokeWidth="3" fill="none">
              <path d="M 120 270 L 200 270 M 190 264 L 200 270 L 190 276" className="animate-pulse" />
              <path d="M 380 230 L 300 230 M 310 224 L 300 230 L 310 236" className="animate-pulse" />
            </g>
          )}

          {/* Center Hub Indicator */}
          <circle cx="250" cy="250" r="18" fill="#131926" stroke="#2d3b59" strokeWidth="2" />
          <text x="250" y="254" fill="#ffffff" fontSize="11" fontWeight="800" textAnchor="middle">C</text>
        </svg>

        {/* Phase Floating Card */}
        <div className="absolute bottom-4 left-4 right-4 bg-[#0d111a]/95 backdrop-blur-md border border-[#1e283d] rounded-xl p-3 flex flex-wrap items-center justify-between gap-3 text-xs shadow-xl">
          <div className="flex items-center gap-2.5">
            <div className={`w-3.5 h-3.5 rounded-full ${nsGreen || ewGreen ? 'bg-emerald-400' : isYellow ? 'bg-amber-400' : 'bg-rose-400'} animate-ping`} />
            <div>
              <span className="text-[#94a3b8] font-medium">Active Phase: </span>
              <span className="font-bold text-white font-mono">
                {isYellow
                  ? 'YELLOW CLEARANCE (3.0s Guardrail)'
                  : phase === 0
                  ? 'PHASE 0: NORTH-SOUTH GREEN'
                  : 'PHASE 2: EAST-WEST GREEN'}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-4 text-[#94a3b8] font-mono">
            {currentStep && (
              <span>Step: <strong className="text-white">{currentStep.step}</strong> ({simTime.toFixed(1)}s)</span>
            )}
            <span>Queue: <strong className="text-blue-400">{currentQueue.toFixed(2)}</strong> veh</span>
            <span>Wait Metric: <strong className="text-amber-400">{waitingTime.toFixed(2)}</strong>s</span>
          </div>
        </div>
      </div>

      {/* Safety Constraint Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-2 text-xs">
        <div className="flex items-center gap-2 p-2 rounded-lg bg-[#0d111a] border border-[#1c2538]">
          <Shield className="w-4 h-4 text-emerald-400 shrink-0" />
          <div>
            <div className="text-[#94a3b8] font-medium text-[11px]">Min Green Safety</div>
            <div className="font-mono font-bold text-emerald-400">5.0s (Hard Barrier)</div>
          </div>
        </div>
        <div className="flex items-center gap-2 p-2 rounded-lg bg-[#0d111a] border border-[#1c2538]">
          <Clock className="w-4 h-4 text-amber-400 shrink-0" />
          <div>
            <div className="text-[#94a3b8] font-medium text-[11px]">Yellow Clearance</div>
            <div className="font-mono font-bold text-amber-400">3.0s (Full TraCI Sub-Step)</div>
          </div>
        </div>
        <div className="flex items-center gap-2 p-2 rounded-lg bg-[#0d111a] border border-[#1c2538]">
          <AlertTriangle className="w-4 h-4 text-blue-400 shrink-0" />
          <div>
            <div className="text-[#94a3b8] font-medium text-[11px]">Max Green Force-Off</div>
            <div className="font-mono font-bold text-blue-400">45.0s (Anti-Starvation)</div>
          </div>
        </div>
      </div>
    </div>
  );
};
