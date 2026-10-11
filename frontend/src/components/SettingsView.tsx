import React from 'react';
import { Settings, Cpu } from 'lucide-react';
import type { RenderQuality } from '../types';

interface SettingsViewProps {
  quality: RenderQuality;
  onQuality: (q: RenderQuality) => void;
}

const QUALITY_OPTIONS: { id: RenderQuality; label: string; hint: string; dpr: string; shadow: string }[] = [
  {
    id: 'high',
    label: 'High Quality',
    hint: 'Crisp resolution and soft shadow filtering',
    dpr: 'DPR 1.0 - 1.75',
    shadow: '2048×2048 Shadow Map',
  },
  {
    id: 'balanced',
    label: 'Balanced (Recommended)',
    hint: 'Optimal performance for Intel 13th Gen Core i5 integrated graphics',
    dpr: 'DPR 1.0 - 1.25',
    shadow: '1024×1024 Shadow Map',
  },
  {
    id: 'low',
    label: 'Low Power / Eco Mode',
    hint: 'Shadows disabled, reduced resolution for minimal battery usage',
    dpr: 'DPR 0.75 - 1.0',
    shadow: 'Shadows Disabled',
  },
];

export const SettingsView: React.FC<SettingsViewProps> = ({ quality, onQuality }) => {
  return (
    <section className="tod-panel tod-glass tod-wide-panel" aria-labelledby="tod-settings-title">
      <header className="tod-panel-head">
        <h2 id="tod-settings-title" className="tod-panel-title">
          <Settings size={18} aria-hidden="true" /> Graphics &amp; Renderer Settings
        </h2>
      </header>

      <fieldset className="tod-quality" style={{ border: 'none', padding: 0, margin: 0 }}>
        <legend className="tod-subcard-title" style={{ marginBottom: '12px' }}>
          3D Intersection Render Quality
        </legend>
        <div className="tod-quality-grid">
          {QUALITY_OPTIONS.map((q) => (
            <label
              key={q.id}
              className="tod-quality-option"
              data-checked={quality === q.id}
              style={{ cursor: 'pointer' }}
            >
              <input
                type="radio"
                name="tod-quality"
                value={q.id}
                checked={quality === q.id}
                onChange={() => onQuality(q.id)}
              />
              <span className="tod-quality-label">{q.label}</span>
              <span className="tod-quality-hint">{q.hint}</span>
              <span
                style={{
                  fontSize: '0.6875rem',
                  color: 'var(--tod-text-3)',
                  marginTop: '6px',
                  display: 'flex',
                  gap: '8px',
                }}
              >
                <span>{q.dpr}</span>
                <span>&bull;</span>
                <span>{q.shadow}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <div
        className="tod-subcard"
        style={{
          marginTop: '16px',
          background: 'rgba(248, 250, 252, 0.7)',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
        }}
      >
        <Cpu size={20} style={{ color: '#059669', flexShrink: 0 }} />
        <div style={{ fontSize: '0.8125rem', color: 'var(--tod-text-2)' }}>
          <strong>Hardware Profile:</strong> Configured for Windows 11 with Intel Core i5 13th-Gen processor, 16 GB RAM, and integrated Intel Iris Xe / UHD Graphics.
          Procedural canvas textures and instanced meshes ensure minimal memory footprint.
        </div>
      </div>
    </section>
  );
};
