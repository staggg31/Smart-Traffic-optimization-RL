/**
 * CameraRig Component
 *
 * Perspective camera controller featuring smooth easing transitions, orbit damping,
 * and calibrated perspective presets.
 *
 * Presets:
 * - 'isometric': [38, 50, 44] looking at [0, 0, 0] — Moderately elevated, closer perspective
 *   keeping all 4 approaches and central stop bars completely in view.
 * - 'top': [0, 96, 0.01] looking at [0, 0, 0] — True bird's-eye orthogonal view for queuing inspection.
 * - 'street': [17, 2.2, 46] looking at [-1, 2.6, 0] — Driver-level perspective for approach dynamics.
 *
 * Controls:
 * - Supports cubic-bezier easing (`easeInOut`) flight animations between presets.
 * - Damped orbit controls (`dampingFactor: 0.08`) with polar constraint preventing underground flipping.
 * - Screenshot capture exporting full canvas raster to PNG.
 */

import { OrbitControls } from '@react-three/drei'
import { useFrame, useThree } from '@react-three/fiber'
import { type ComponentRef, useEffect, useRef } from 'react'
import * as THREE from 'three'
import type { CameraCommand, CameraPreset } from '../types'

type OrbitControlsImpl = ComponentRef<typeof OrbitControls>

export const CAMERA_PRESETS: Record<CameraPreset, { position: [number, number, number]; target: [number, number, number] }> = {
  isometric: { position: [38, 50, 44], target: [0, 0, 0] },
  top: { position: [0, 96, 0.01], target: [0, 0, 0] },
  street: { position: [17, 2.2, 46], target: [-1, 2.6, 0] },
}

type Flight = { fromPos: THREE.Vector3; fromTarget: THREE.Vector3; toPos: THREE.Vector3; toTarget: THREE.Vector3; t: number; duration: number }

const easeInOut = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2)

export function CameraRig({ preset, command }: { preset: CameraPreset; command: CameraCommand | null }) {
  const controls = useRef<OrbitControlsImpl>(null)
  const flight = useRef<Flight | null>(null)
  const { camera, gl, scene } = useThree()

  const flyTo = (pos: THREE.Vector3, target: THREE.Vector3, duration = 1.1) => {
    const c = controls.current
    if (!c) return
    flight.current = { fromPos: camera.position.clone(), fromTarget: c.target.clone(), toPos: pos, toTarget: target, t: 0, duration }
  }

  useEffect(() => {
    const p = CAMERA_PRESETS[preset]
    flyTo(new THREE.Vector3(...p.position), new THREE.Vector3(...p.target))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preset])

  useEffect(() => {
    if (!command || !controls.current) return
    const target = controls.current.target.clone()
    if (command.type === 'reset') {
      const p = CAMERA_PRESETS[preset]
      flyTo(new THREE.Vector3(...p.position), new THREE.Vector3(...p.target))
    } else if (command.type === 'zoomIn' || command.type === 'zoomOut') {
      const factor = command.type === 'zoomIn' ? 0.75 : 1.33
      const offset = camera.position.clone().sub(target).multiplyScalar(factor)
      const len = THREE.MathUtils.clamp(offset.length(), 8, 220)
      flyTo(target.clone().add(offset.setLength(len)), target, 0.45)
    } else if (command.type === 'screenshot') {
      gl.render(scene, camera)
      const link = document.createElement('a')
      link.download = `traffic-opt-rl-${Date.now()}.png`
      link.href = gl.domElement.toDataURL('image/png')
      link.click()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [command])

  useFrame((_, delta) => {
    const f = flight.current
    const c = controls.current
    if (!f || !c) return
    f.t = Math.min(1, f.t + delta / f.duration)
    const k = easeInOut(f.t)
    camera.position.lerpVectors(f.fromPos, f.toPos, k)
    c.target.lerpVectors(f.fromTarget, f.toTarget, k)
    c.update()
    if (f.t >= 1) flight.current = null
  })

  return (
    <OrbitControls
      ref={controls}
      makeDefault
      enableDamping
      dampingFactor={0.08}
      minDistance={8}
      maxDistance={220}
      maxPolarAngle={Math.PI / 2 - 0.04}
      target={CAMERA_PRESETS.isometric.target}
      onStart={() => {
        flight.current = null
      }}
    />
  )
}
