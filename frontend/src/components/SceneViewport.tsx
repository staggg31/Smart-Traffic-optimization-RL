/**
 * SceneViewport Component
 *
 * Viewport container hosting the Three.js React Three Fiber 3D intersection centerpiece.
 *
 * Visual & Interactive Features:
 * - Clear labeling: "Procedural 3D Kinematics (Illustrative)" distinguishes the illustrative
 *   viewport animation from the authentic SUMO TraCI runner
 * - Floating glassmorphism chips displaying live signal phase, clearance stage, and vehicle counter
 * - Camera control toolbar: Zoom In, Zoom Out, Reset Camera, Screenshot Capture, Top-Down toggle
 * - Generous viewport height (`clamp(480px, 63vh, 760px)`) with unobstructed view of all 4 approaches
 */

import React from 'react';
import { Camera, Map as MapIcon, Minus, Plus, RotateCcw } from 'lucide-react';
import { IntersectionScene, type IntersectionSceneProps } from '../scene/IntersectionScene';
import type { CameraCommandType, LiveSceneStats } from '../types';

interface SceneViewportProps extends IntersectionSceneProps {
  stats: LiveSceneStats | null;
  onCommand: (type: CameraCommandType) => void;
  onTopDown: () => void;
}

const STAGE_LABEL = { green: 'Green Phase', yellow: 'Yellow Clearance (3s)', allred: 'All-Red' } as const;

export const SceneViewport: React.FC<SceneViewportProps> = ({
  stats,
  onCommand,
  onTopDown,
  ...sceneProps
}) => {
  return (
    <section className="tod-scene tod-glass" aria-label="3D traffic intersection visualization">
      <IntersectionScene {...sceneProps} />

      {/* Top Left Status Badge */}
      <div className="tod-scene-chip tod-scene-chip-tl">
        <span
          className={`tod-dot ${sceneProps.playing ? 'tod-dot-green tod-dot-pulse' : 'tod-dot-amber'}`}
          aria-hidden="true"
        />
        <span>{sceneProps.playing ? 'Animating' : 'Paused'} &middot; Procedural 3D Kinematics (Illustrative)</span>
      </div>

      {/* Top Right Camera Interaction Bar */}
      <div className="tod-scene-tools" role="toolbar" aria-label="3D camera tools">
        <button
          type="button"
          className="tod-scene-btn"
          aria-label="Save screenshot"
          title="Export high-resolution screenshot"
          onClick={() => onCommand('screenshot')}
        >
          <Camera size={16} aria-hidden="true" />
        </button>
        <button
          type="button"
          className="tod-scene-btn"
          aria-label="Top-down view"
          title="Switch to orthogonal top-down view"
          onClick={onTopDown}
        >
          <MapIcon size={16} aria-hidden="true" />
        </button>
        <span className="tod-scene-tools-sep" aria-hidden="true" />
        <button
          type="button"
          className="tod-scene-btn"
          aria-label="Zoom in"
          title="Zoom camera closer"
          onClick={() => onCommand('zoomIn')}
        >
          <Plus size={16} aria-hidden="true" />
        </button>
        <button
          type="button"
          className="tod-scene-btn"
          aria-label="Zoom out"
          title="Zoom camera back"
          onClick={() => onCommand('zoomOut')}
        >
          <Minus size={16} aria-hidden="true" />
        </button>
        <button
          type="button"
          className="tod-scene-btn"
          aria-label="Reset camera"
          title="Reset camera to default isometric view"
          onClick={() => onCommand('reset')}
        >
          <RotateCcw size={16} aria-hidden="true" />
        </button>
      </div>

      {/* Bottom Left Live Kinematic Stats Overlay */}
      {stats && (
        <div className="tod-scene-chip tod-scene-chip-bl" aria-live="off">
          <span className={`tod-signal-dot tod-signal-${stats.stage}`} aria-hidden="true" />
          <span>
            {stats.phaseLabel} &middot; {STAGE_LABEL[stats.stage]}
          </span>
          <span className="tod-chip-sep" aria-hidden="true" />
          <span>{stats.vehicles} demo veh</span>
          <span className="tod-chip-sep" aria-hidden="true" />
          <span>{stats.queued} queued</span>
          <span className="tod-chip-sep" aria-hidden="true" />
          <span className="tod-mono">t {stats.simTime}</span>
        </div>
      )}
    </section>
  );
};
