import { useFrame, useThree } from '@react-three/fiber'
import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'
import type { CameraCommand, CameraPreset, LiveSceneStats, RenderQuality } from '../types'
import { CameraRig } from './CameraRig'
import { CityBlocks } from './CityBlocks'
import { RoadNetwork } from './RoadNetwork'
import { PHASE_LABEL, type TrafficSimulation } from './simulation'
import { TrafficSignals } from './TrafficSignals'
import { VehicleFleet } from './VehicleFleet'

const SKY = '#dfe9f2'

function StudioEnvironment() {
  const { gl, scene } = useThree()
  useEffect(() => {
    const pmrem = new THREE.PMREMGenerator(gl)
    const env = pmrem.fromScene(new RoomEnvironment(), 0.04).texture
    scene.environment = env
    scene.environmentIntensity = 0.55
    return () => {
      scene.environment = null
      env.dispose()
      pmrem.dispose()
    }
  }, [gl, scene])
  return null
}

function StatsReporter({ sim, onStats }: { sim: TrafficSimulation; onStats?: (s: LiveSceneStats) => void }) {
  const acc = useRef(0)
  useFrame((_, delta) => {
    acc.current += delta
    if (acc.current < 0.5 || !onStats) return
    acc.current = 0
    const m = Math.floor(sim.time / 60)
    const s = Math.floor(sim.time % 60)
    onStats({
      simTime: `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`,
      vehicles: sim.vehicles.length,
      queued: sim.queuedCount(),
      completed: sim.completed,
      phaseLabel: PHASE_LABEL[sim.phase],
      stage: sim.stage,
      violations: sim.violations,
    })
  })
  return null
}

const SHADOW_SIZE: Record<RenderQuality, number> = { high: 2048, balanced: 1024, low: 512 }

export interface SceneContentsProps {
  sim: TrafficSimulation
  playing: boolean
  speed: number
  preset: CameraPreset
  command: CameraCommand | null
  quality: RenderQuality
  onStats?: (s: LiveSceneStats) => void
}

export function SceneContents({ sim, playing, speed, preset, command, quality, onStats }: SceneContentsProps) {
  const shadowSize = SHADOW_SIZE[quality]
  return (
    <>
      <color attach="background" args={[SKY]} />
      <fog attach="fog" args={[SKY, 130, 300]} />
      <StudioEnvironment />
      <hemisphereLight args={['#eef4ff', '#b7b1a3', 1.05]} />
      <directionalLight
        key={shadowSize}
        position={[45, 85, 60]}
        intensity={2.4}
        color="#fff6ea"
        castShadow={quality !== 'low'}
        shadow-mapSize={[shadowSize, shadowSize]}
        shadow-camera-left={-85}
        shadow-camera-right={85}
        shadow-camera-top={85}
        shadow-camera-bottom={-85}
        shadow-camera-near={10}
        shadow-camera-far={260}
        shadow-bias={-0.0004}
        shadow-normalBias={0.04}
      />
      <RoadNetwork />
      <CityBlocks />
      <TrafficSignals sim={sim} />
      <VehicleFleet sim={sim} playing={playing} speed={speed} />
      <StatsReporter sim={sim} onStats={onStats} />
      <CameraRig preset={preset} command={command} />
    </>
  )
}
