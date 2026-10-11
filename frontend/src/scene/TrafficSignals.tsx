/**
 * TrafficSignals Component
 *
 * Renders the 4 mast-arm traffic signal gantries and signal heads at each approach.
 *
 * Signal Control State Integration:
 * - Monitors the active signal phase of the simulation
 * - Dynamically updates emissive intensities of red, yellow, and green lenses
 * - Visualizes transition stages: Green hold, Yellow clearance (3s), and All-Red intervals
 * - Mast-arm gantry poles are positioned with realistic offsets and heights over the roadway
 */

import { useFrame } from '@react-three/fiber'
import { useMemo } from 'react'
import * as THREE from 'three'
import { APPROACHES, APPROACH_HEADING, type ApproachId, ROAD_HALF_WIDTH, SIDEWALK_HEIGHT, STOP_LINE_DISTANCE, armPoint, headingToYaw, laneOffset, rightOf } from './layout'
import { box, cylinder, standardMaterial } from './materials'
import type { SignalColor, TrafficSimulation } from './simulation'

const LAMP_COLORS: Record<SignalColor, string> = { red: '#ff2b2b', yellow: '#ffb020', green: '#19e07a' }
const ORDER: SignalColor[] = ['red', 'yellow', 'green']

type HeadMaterials = Record<SignalColor, THREE.MeshStandardMaterial>

function makeHeadMaterials(): HeadMaterials {
  const m = {} as HeadMaterials
  for (const c of ORDER) {
    m[c] = new THREE.MeshStandardMaterial({ color: '#1b1d20', emissive: LAMP_COLORS[c], emissiveIntensity: 0.05, roughness: 0.3 })
  }
  return m
}

function SignalHead({ materials, position, yaw }: { materials: HeadMaterials; position: [number, number, number]; yaw: number }) {
  const housing = standardMaterial('#2b2f34', 0.55, 0.3)
  const lamp = cylinder(0.13, 0.13, 0.06, 16)
  return (
    <group position={position} rotation={[0, yaw, 0]}>
      <mesh castShadow geometry={box(0.42, 1.22, 0.32)} material={housing} />
      <mesh position={[0, 0, -0.18]} geometry={box(0.62, 1.42, 0.04)} material={standardMaterial('#202327', 0.7)} />
      {ORDER.map((c, i) => (
        <group key={c} position={[0, 0.38 - i * 0.38, 0.17]}>
          <mesh rotation={[Math.PI / 2, 0, 0]} geometry={lamp} material={materials[c]} />
          <mesh position={[0, 0.13, 0.1]} geometry={box(0.32, 0.03, 0.22)} material={housing} />
        </group>
      ))}
    </group>
  )
}

function SignalMast({ approach, through, left }: { approach: ApproachId; through: HeadMaterials; left: HeadMaterials }) {
  const d = APPROACH_HEADING[approach]
  const r = rightOf(d)
  const poleOffset = ROAD_HALF_WIDTH + 1.7
  const along = STOP_LINE_DISTANCE + 1.4
  const pole = armPoint(d, along, poleOffset)
  const armEnd = 0.6
  const armMid = armPoint(d, along, (poleOffset + armEnd) / 2)
  const faceYaw = headingToYaw({ x: -d.x, z: -d.z })
  const metal = standardMaterial('#7a828b', 0.4, 0.7)
  const height = 6.4
  return (
    <group>
      <mesh castShadow position={[pole.x, SIDEWALK_HEIGHT + height / 2, pole.z]} geometry={cylinder(0.14, 0.2, height, 12)} material={metal} />
      <mesh castShadow position={[armMid.x, SIDEWALK_HEIGHT + height - 0.2, armMid.z]} rotation={[0, headingToYaw(r), 0]} geometry={box(0.18, 0.2, poleOffset - armEnd)} material={metal} />
      {[0, 1, 2].map((lane) => {
        const p = armPoint(d, along, laneOffset(lane))
        return <SignalHead key={lane} materials={lane === 0 ? left : through} position={[p.x, SIDEWALK_HEIGHT + height - 1.0, p.z]} yaw={faceYaw} />
      })}
      <SignalHead key="pole-mount" materials={through} position={[pole.x - d.x * 0.3, SIDEWALK_HEIGHT + 3.1, pole.z - d.z * 0.3]} yaw={faceYaw} />
      {(() => {
        const s = armPoint(d, along, poleOffset - 2.2)
        return <mesh position={[s.x, SIDEWALK_HEIGHT + height + 0.25, s.z]} rotation={[0, headingToYaw(r), 0]} geometry={box(0.05, 0.42, 2.1)} material={standardMaterial('#1f6b45', 0.5)} />
      })()}
    </group>
  )
}

export function TrafficSignals({ sim }: { sim: TrafficSimulation }) {
  const mats = useMemo(() => {
    const out = {} as Record<ApproachId, { through: HeadMaterials; left: HeadMaterials }>
    for (const a of APPROACHES) out[a] = { through: makeHeadMaterials(), left: makeHeadMaterials() }
    return out
  }, [])

  useFrame(() => {
    for (const a of APPROACHES) {
      const t = sim.signalFor(a, 1)
      const l = sim.signalFor(a, 0)
      for (const c of ORDER) {
        mats[a].through[c].emissiveIntensity = c === t ? 3.2 : 0.05
        mats[a].left[c].emissiveIntensity = c === l ? 3.2 : 0.05
      }
    }
  })

  return (
    <>
      {APPROACHES.map((a) => (
        <SignalMast key={a} approach={a} through={mats[a].through} left={mats[a].left} />
      ))}
    </>
  )
}
