/**
 * VehicleFleet Component
 *
 * Manages the rendered vehicle fleet in the 3D scene:
 * - Dynamic Roster Sync: Listens for spawn and despawn events in the simulation
 * - Kinematic Updates: In `useFrame`, updates vehicle positions (x, y, z), yaw headings,
 *   wheel rotation speeds proportional to forward velocity, and dynamic brake lights
 * - Multi-Class Fleet: Supports sedans, SUVs, trucks, and buses with varied paint colors
 */

import { useFrame } from '@react-three/fiber'
import { useCallback, useEffect, useRef, useState } from 'react'
import type * as THREE from 'three'
import type { TrafficSimulation, VehicleKind } from './simulation'
import { VehicleModel } from './VehicleModels'

type RosterItem = { id: number; kind: VehicleKind; color: string }
type Rig = { group: THREE.Group; wheels: THREE.Object3D[]; tails: THREE.MeshStandardMaterial[] }

const toRoster = (sim: TrafficSimulation): RosterItem[] => sim.vehicles.map(({ id, kind, color }) => ({ id, kind, color }))

interface VehicleFleetProps {
  sim: TrafficSimulation
  playing: boolean
  speed: number
}

/** Steps the illustrative simulation and mirrors its state onto vehicle meshes. */
export function VehicleFleet({ sim, playing, speed }: VehicleFleetProps) {
  const [roster, setRoster] = useState<RosterItem[]>(() => toRoster(sim))
  const rigs = useRef(new Map<number, Rig>())

  useEffect(() => {
    sim.onRosterChange = () => setRoster(toRoster(sim))
    return () => {
      sim.onRosterChange = undefined
    }
  }, [sim])

  const register = useCallback(
    (id: number) => (group: THREE.Group | null) => {
      if (!group) {
        rigs.current.delete(id)
        return
      }
      const wheels: THREE.Object3D[] = []
      const tails: THREE.MeshStandardMaterial[] = []
      group.traverse((o) => {
        if (o.name === 'wheel') wheels.push(o)
        if (o.name === 'tail') tails.push((o as THREE.Mesh).material as THREE.MeshStandardMaterial)
      })
      const v = sim.vehicles.find((x) => x.id === id)
      if (v) {
        group.position.set(v.x, 0, v.z)
        group.rotation.y = v.yaw
      }
      rigs.current.set(id, { group, wheels, tails })
    },
    [sim],
  )

  useFrame((_, delta) => {
    if (playing) sim.step(delta * speed)
    for (const v of sim.vehicles) {
      const rig = rigs.current.get(v.id)
      if (!rig) continue
      rig.group.position.set(v.x, 0.01, v.z)
      rig.group.rotation.y = v.yaw
      for (const w of rig.wheels) w.rotation.x = v.wheelAngle
      const braking = v.acc < -0.8 || v.v < 0.4
      for (const m of rig.tails) m.emissiveIntensity = braking ? 2.4 : 0.4
    }
  })

  return (
    <group>
      {roster.map((r) => (
        <group key={r.id} ref={register(r.id)}>
          <VehicleModel kind={r.kind} color={r.color} />
        </group>
      ))}
    </group>
  )
}
