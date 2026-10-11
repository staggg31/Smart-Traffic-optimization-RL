/**
 * IntersectionScene Component
 *
 * Root React Three Fiber Canvas mounting the 3D smart-city intersection.
 *
 * Robustness & Performance Design:
 * - WebGL Feature Detection: Gracefully falls back to 2D topological diagram if WebGL is unavailable
 * - SceneErrorBoundary: Isolates 3D WebGL rendering exceptions without breaking the host React app
 * - Dynamic Quality Scaling: Adjusts DPR (devicePixelRatio) and shadow maps for integrated GPUs:
 *     - 'high': dpr [1, 2], shadow map 2048x2048
 *     - 'balanced': dpr [1, 1.5], shadow map 1024x1024 (recommended for Intel Iris/UHD)
 *     - 'low': dpr 1, shadows disabled
 */

import { Canvas } from '@react-three/fiber'
import { Component, type ReactNode, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react'
import type {
  CameraCommand,
  CameraPreset,
  ControllerId,
  LiveSceneStats,
  RenderQuality,
  SafetyConstraints,
  Scenario,
  ScenarioInfo,
  SceneEvent,
} from '../types'
import { CAMERA_PRESETS } from './CameraRig'
import { SceneContents } from './SceneContents'
import { TrafficSimulation } from './simulation'

export interface IntersectionSceneProps {
  scenario: Scenario | (ScenarioInfo & { demand?: { ns: number; ew: number } })
  controller: ControllerId | 'FixedTime' | 'Actuated' | 'PPO'
  constraints?: SafetyConstraints | { min_green_seconds: number; yellow_clearance_seconds: number; max_green_seconds: number; all_red_seconds?: number }
  playing: boolean
  speed: number
  preset: CameraPreset
  command: CameraCommand | null
  resetToken: number
  quality: RenderQuality
  onEvent?: (e: SceneEvent) => void
  onStats?: (s: LiveSceneStats) => void
}

class SceneErrorBoundary extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() {
    return { failed: true }
  }
  componentDidCatch(error: unknown) {
    console.error('[traffic-dashboard] 3D scene failed to render', error)
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children
  }
}

let webglSupport: boolean | null = null
function detectWebGL() {
  if (webglSupport === null) {
    try {
      const c = document.createElement('canvas')
      webglSupport = Boolean(c.getContext('webgl2') || c.getContext('webgl'))
    } catch {
      webglSupport = false
    }
  }
  return webglSupport
}
const noopSubscribe = () => () => {}

function SceneFallback({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="tod-scene-fallback" role="status">
      <p className="tod-scene-fallback-title">{title}</p>
      <p className="tod-scene-fallback-detail">{detail}</p>
    </div>
  )
}

const DPR: Record<RenderQuality, [number, number]> = { high: [1, 1.75], balanced: [1, 1.25], low: [0.75, 1] }

function normalizeController(c: string): ControllerId {
  if (c === 'FixedTime') return 'fixed'
  if (c === 'Actuated') return 'actuated'
  if (c === 'PPO') return 'ppo'
  return (c as ControllerId) || 'ppo'
}

function normalizeConstraints(c?: any): SafetyConstraints {
  if (!c) return { minGreen: 5, yellow: 3, allRed: 0, maxGreen: 45 }
  return {
    minGreen: c.minGreen ?? c.min_green_seconds ?? 5,
    yellow: c.yellow ?? c.yellow_clearance_seconds ?? 3,
    allRed: c.allRed ?? c.all_red_seconds ?? 0,
    maxGreen: c.maxGreen ?? c.max_green_seconds ?? 45,
  }
}

export function IntersectionScene(props: IntersectionSceneProps) {
  const { scenario, controller: rawCtrl, constraints: rawConstraints, resetToken, onEvent, quality } = props
  const webgl = useSyncExternalStore(noopSubscribe, detectWebGL, () => null)
  const [ready, setReady] = useState(false)

  const controller = normalizeController(rawCtrl)
  const constraints = normalizeConstraints(rawConstraints)
  const controllerRef = useRef(controller)
  controllerRef.current = controller

  const demand = (scenario as any).demand || {
    ns: ((scenario as any).vehicle_count ? (scenario as any).vehicle_count / 80 : 1) * 0.16,
    ew: ((scenario as any).vehicle_count ? (scenario as any).vehicle_count / 80 : 1) * 0.12,
  }

  const sim = useMemo(
    () => new TrafficSimulation({ seed: scenario.seed, demand, controller: controllerRef.current, constraints }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [scenario.id, resetToken, constraints.minGreen, constraints.yellow, constraints.maxGreen],
  )

  useEffect(() => {
    sim.setController(controller)
  }, [sim, controller])

  useEffect(() => {
    sim.onEvent = onEvent
    return () => {
      sim.onEvent = undefined
    }
  }, [sim, onEvent])

  if (webgl === false) {
    return <SceneFallback title="3D view unavailable" detail="WebGL is not supported or is disabled in this browser. Metrics and analytics below remain available." />
  }

  return (
    <SceneErrorBoundary fallback={<SceneFallback title="3D scene failed to load" detail="The renderer hit an error. Try lowering render quality in Settings or reloading the page." />}>
      {webgl && (
        <Canvas
          shadows={quality !== 'low'}
          dpr={DPR[quality]}
          gl={{ antialias: quality !== 'low', preserveDrawingBuffer: true, powerPreference: 'high-performance' }}
          camera={{ fov: 30, near: 0.5, far: 700, position: CAMERA_PRESETS.isometric.position }}
          onCreated={() => setReady(true)}
          aria-label="Interactive 3D intersection visual prototype"
        >
          <SceneContents
            sim={sim}
            playing={props.playing}
            speed={props.speed}
            preset={props.preset}
            command={props.command}
            quality={quality}
            onStats={props.onStats}
          />
        </Canvas>
      )}
      {!ready && (
        <div className="tod-scene-loading" role="status">
          <span className="tod-spinner" aria-hidden="true" />
          Building intersection scene…
        </div>
      )}
    </SceneErrorBoundary>
  )
}
