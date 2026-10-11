import { memo, useMemo } from 'react'
import * as THREE from 'three'
import type { VehicleKind } from './simulation'
import { box, cylinder, glassMaterial, paintMaterial, roundedBox, standardMaterial } from './materials'

/**
 * Procedural vehicle models. Local frame: +z = forward, y = 0 is the road
 * surface, wheel centres sit at y = radius so tyres touch the ground.
 * Wheels are groups named "wheel" so the fleet can roll them about +x.
 */

const tyre = () => standardMaterial('#16181b', 0.85)
const rim = () => standardMaterial('#c3c8ce', 0.3, 0.85)
const trim = () => standardMaterial('#22262b', 0.6, 0.2)
const headlight = () => standardMaterial('#f4f7fb', 0.2, 0.1, '#fff6e0', 0.9)

function Wheel({ x, z, radius, width }: { x: number; z: number; radius: number; width: number }) {
  return (
    <group position={[x, radius, z]} name="wheel">
      <group rotation={[0, 0, Math.PI / 2]}>
        <mesh geometry={cylinder(radius, radius, width, 22)} material={tyre()} />
        <mesh geometry={cylinder(radius * 0.62, radius * 0.62, width + 0.02, 18)} material={rim()} />
        <mesh geometry={box(radius * 1.12, width + 0.04, 0.07)} material={trim()} />
        <mesh geometry={box(0.07, width + 0.04, radius * 1.12)} material={trim()} />
        <mesh geometry={cylinder(radius * 0.16, radius * 0.16, width + 0.06, 10)} material={rim()} />
      </group>
    </group>
  )
}

function WheelSet({ track, axles, radius, width }: { track: number; axles: number[]; radius: number; width: number }) {
  return (
    <>
      {axles.map((z) => (
        <group key={z}>
          <Wheel x={track} z={z} radius={radius} width={width} />
          <Wheel x={-track} z={z} radius={radius} width={width} />
        </group>
      ))}
    </>
  )
}

function Lamps({ halfX, y, front, rear, tail, size = [0.36, 0.11] }: { halfX: number; y: number; front: number; rear: number; tail: THREE.Material; size?: [number, number] }) {
  return (
    <>
      {[halfX, -halfX].map((x, i) => (
        <group key={i}>
          <mesh position={[x, y, front]} geometry={box(size[0], size[1], 0.06)} material={headlight()} />
          <mesh name="tail" position={[x, y + 0.02, rear]} geometry={box(size[0] + 0.04, size[1] + 0.02, 0.06)} material={tail} />
        </group>
      ))}
    </>
  )
}

function useTailMaterial() {
  return useMemo(
    () => new THREE.MeshStandardMaterial({ color: '#7a0d12', emissive: '#ff1f1f', emissiveIntensity: 0.4, roughness: 0.35 }),
    [],
  )
}

function Sedan({ color, taxi = false }: { color: string; taxi?: boolean }) {
  const tail = useTailMaterial()
  const L = 4.6
  const W = 1.84
  const paint = paintMaterial(color)
  return (
    <group>
      <mesh castShadow position={[0, 0.56, 0]} geometry={roundedBox(W, 0.62, L, 0.16)} material={paint} />
      <mesh castShadow position={[0, 1.09, -0.2]} geometry={roundedBox(W * 0.84, 0.5, 2.35, 0.18)} material={glassMaterial()} />
      <mesh position={[0, 1.35, -0.25]} geometry={roundedBox(W * 0.8, 0.07, 1.85, 0.03)} material={paint} />
      <mesh position={[0, 0.38, L / 2 - 0.03]} geometry={box(W * 0.96, 0.22, 0.12)} material={trim()} />
      <mesh position={[0, 0.38, -L / 2 + 0.03]} geometry={box(W * 0.96, 0.22, 0.12)} material={trim()} />
      <mesh position={[0, 0.6, L / 2 + 0.01]} geometry={box(0.8, 0.14, 0.04)} material={trim()} />
      {[1, -1].map((s) => (
        <mesh key={s} position={[s * (W / 2 + 0.07), 0.98, 0.85]} geometry={box(0.2, 0.12, 0.09)} material={paint} />
      ))}
      <Lamps halfX={0.6} y={0.72} front={L / 2 - 0.02} rear={-L / 2 + 0.02} tail={tail} />
      {taxi && (
        <>
          <mesh position={[0, 1.49, -0.3]} geometry={roundedBox(0.72, 0.2, 0.3, 0.04)} material={standardMaterial('#fbfbf7', 0.4, 0, '#fff4c2', 0.5)} />
          <mesh position={[0, 0.72, 0]} geometry={box(W + 0.01, 0.07, L * 0.62)} material={trim()} />
        </>
      )}
      <WheelSet track={W / 2 - 0.1} axles={[1.38, -1.38]} radius={0.33} width={0.24} />
    </group>
  )
}

function Suv({ color }: { color: string }) {
  const tail = useTailMaterial()
  const L = 4.85
  const W = 1.95
  const paint = paintMaterial(color)
  return (
    <group>
      <mesh castShadow position={[0, 0.69, 0]} geometry={roundedBox(W, 0.78, L, 0.18)} material={paint} />
      <mesh castShadow position={[0, 1.36, -0.32]} geometry={roundedBox(W * 0.88, 0.62, 2.95, 0.16)} material={glassMaterial()} />
      <mesh position={[0, 1.69, -0.38]} geometry={roundedBox(W * 0.86, 0.07, 2.7, 0.03)} material={paint} />
      {[1, -1].map((s) => (
        <group key={s}>
          <mesh position={[s * 0.68, 1.76, -0.38]} geometry={box(0.06, 0.06, 2.3)} material={trim()} />
          <mesh position={[s * (W / 2 + 0.07), 1.18, 0.95]} geometry={box(0.2, 0.13, 0.09)} material={paint} />
        </group>
      ))}
      <mesh position={[0, 0.42, L / 2 - 0.03]} geometry={box(W * 0.96, 0.26, 0.14)} material={trim()} />
      <mesh position={[0, 0.42, -L / 2 + 0.03]} geometry={box(W * 0.96, 0.26, 0.14)} material={trim()} />
      <mesh position={[0, 0.74, L / 2 + 0.01]} geometry={box(0.95, 0.2, 0.04)} material={trim()} />
      <Lamps halfX={0.66} y={0.9} front={L / 2 - 0.02} rear={-L / 2 + 0.02} tail={tail} />
      <WheelSet track={W / 2 - 0.12} axles={[1.45, -1.45]} radius={0.38} width={0.27} />
    </group>
  )
}

function DeliveryTruck({ color }: { color: string }) {
  const tail = useTailMaterial()
  const L = 6.8
  const W = 2.25
  const cab = paintMaterial('#e6e8e6')
  const cargo = standardMaterial(color, 0.55)
  return (
    <group>
      <mesh position={[0, 0.58, 0]} geometry={box(1.5, 0.26, 6.3)} material={trim()} />
      <mesh castShadow position={[0, 1.42, L / 2 - 0.98]} geometry={roundedBox(W, 1.9, 1.9, 0.2)} material={cab} />
      <mesh position={[0, 1.88, L / 2 - 0.03]} geometry={box(W * 0.86, 0.72, 0.06)} material={glassMaterial()} />
      <mesh position={[0, 1.88, L / 2 - 1.05]} geometry={box(W + 0.02, 0.6, 0.95)} material={glassMaterial()} />
      <mesh castShadow position={[0, 1.92, -0.95]} geometry={roundedBox(2.35, 2.6, 4.6, 0.06)} material={cargo} />
      <mesh position={[0, 1.15, -0.95]} geometry={box(2.37, 0.32, 4.62)} material={standardMaterial('#2f6db5', 0.5)} />
      <mesh position={[0, 0.5, L / 2 + 0.02]} geometry={box(W * 0.98, 0.26, 0.14)} material={trim()} />
      {[1, -1].map((s) => (
        <mesh key={s} position={[s * (W / 2 + 0.1), 1.95, L / 2 - 0.6]} geometry={box(0.06, 0.32, 0.18)} material={trim()} />
      ))}
      <Lamps halfX={0.82} y={0.82} front={L / 2 + 0.01} rear={-3.27} tail={tail} size={[0.32, 0.14]} />
      <WheelSet track={W / 2 - 0.16} axles={[2.35, -1.55, -2.6]} radius={0.45} width={0.3} />
    </group>
  )
}

function CityBus({ color }: { color: string }) {
  const tail = useTailMaterial()
  const L = 12
  const W = 2.55
  const paint = paintMaterial(color)
  return (
    <group>
      <mesh castShadow position={[0, 1.73, 0]} geometry={roundedBox(W, 2.76, L, 0.24)} material={paint} />
      <mesh position={[0, 2.18, -0.3]} geometry={box(W + 0.03, 1.0, L - 1.7)} material={glassMaterial()} />
      <mesh position={[0, 2.0, L / 2 + 0.005]} geometry={box(W * 0.9, 1.45, 0.04)} material={glassMaterial()} />
      <mesh position={[0, 2.92, L / 2 + 0.02]} geometry={box(1.6, 0.22, 0.04)} material={standardMaterial('#2a2a2a', 0.4, 0, '#ffb547', 0.9)} />
      <mesh position={[0, 3.14, 0]} geometry={roundedBox(W * 0.97, 0.12, L * 0.97, 0.05)} material={standardMaterial('#eef1f4', 0.5)} />
      <mesh castShadow position={[0, 3.34, -2]} geometry={roundedBox(1.6, 0.32, 2.8, 0.08)} material={standardMaterial('#dfe4e9', 0.5)} />
      <mesh position={[0, 0.56, 0]} geometry={box(W + 0.01, 0.36, L - 0.3)} material={standardMaterial('#e9edf2', 0.5)} />
      {[4.3, 0.2].map((z) => (
        <mesh key={z} position={[-(W / 2 + 0.012), 1.5, z]} geometry={box(0.03, 2.05, 1.15)} material={glassMaterial()} />
      ))}
      <mesh position={[0, 0.5, L / 2 + 0.03]} geometry={box(W * 0.98, 0.3, 0.1)} material={trim()} />
      <Lamps halfX={0.95} y={0.85} front={L / 2 + 0.01} rear={-L / 2 - 0.01} tail={tail} size={[0.34, 0.16]} />
      <WheelSet track={W / 2 - 0.2} axles={[3.65, -3.4]} radius={0.5} width={0.32} />
    </group>
  )
}

export const VehicleModel = memo(function VehicleModel({ kind, color }: { kind: VehicleKind; color: string }) {
  switch (kind) {
    case 'sedan':
      return <Sedan color={color} />
    case 'taxi':
      return <Sedan color={color} taxi />
    case 'suv':
      return <Suv color={color} />
    case 'truck':
      return <DeliveryTruck color={color} />
    case 'bus':
      return <CityBus color={color} />
  }
})
