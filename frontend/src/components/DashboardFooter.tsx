import React from 'react';
import { Info } from 'lucide-react';

export const DashboardFooter: React.FC = () => {
  return (
    <footer className="tod-footer tod-glass">
      <div className="tod-footer-note">
        <Info size={16} className="tod-footer-icon" aria-hidden="true" />
        <span>
          <strong>Research Disclaimer:</strong> The 3D intersection centerpiece provides a procedural kinematic simulation for visual inspection of traffic dynamics and signal phases.
          Authoritative performance metrics, training curves, and held-out evaluation comparisons are derived directly from real SUMO TraCI episodes and the trained 30,000-step PPO model.
        </span>
      </div>
      <div className="tod-footer-meta">
        <span>Traffic-Opt-RL Research System</span>
        <span aria-hidden="true">|</span>
        <span>SUMO 1.28.0 &bull; SB3 2.5.0 &bull; PyTorch 2.5.1 &bull; FastAPI 0.143.0</span>
      </div>
    </footer>
  );
};
