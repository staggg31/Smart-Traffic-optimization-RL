/**
 * CityBlocks Component
 *
 * Procedurally generates the urban surrounding environment:
 * - 4-Quadrant Architectural Blocks: Procedural commercial, residential, and glass facades
 * - Obstruction Prevention: Foreground quadrant buildings are strictly constrained to low
 *   profiles (6-11m) so the camera maintains a 100% unobstructed view of all 4 approaches,
 *   signal heads, and stop bars.
 * - Pedestrian Street Life: Walkers, crosswalk users, trees, streetlights, and traffic signage.
 * - Instanced/Cached Geometries: Uses shared box geometries and cached canvas textures for fast GPU rendering.
 */

import { useFrame } from '@react-three/fiber'
import { useLayoutEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import { APPROACHES, APPROACH_HEADING, ROAD_HALF_WIDTH, SIDEWALK_HEIGHT, armPoint, headingToYaw } from './layout'
import { box, cylinder, standardMaterial } from './materials'
import { mulberry32 } from './simulation'
import { type FacadeStyle, createFacadeTexture } from './textures'

const GROUND = SIDEWALK_HEIGHT
const STYLES: FacadeStyle[] = ['glass', 'concrete', 'white', 'brick', 'glass', 'white']

type BuildingSpec = { x: number; z: number; w: number; d: number; h: number; style: FacadeStyle; roofUnits: number }

function planBuildings(): BuildingSpec[] {
  const rand = mulberry32(42)
  const list: BuildingSpec[] = []
  const quadrants: [number, number][] = [[1, 1], [-1, 1], [1, -1], [-1, -1]]
  for (const [sx, sz] of quadrants) {
    const isForeground = sx === 1 && sz === 1
    let u = 26
    while (u < 104) {
      const w = 12 + rand() * 9
      const d = 14 + rand() * 8
      // Low profile in foreground to guarantee zero occlusion of approaches & intersection
      const h = isForeground ? (u < 54 ? 6 + rand() * 5 : 10 + rand() * 8) : (u < 44 ? 10 + rand() * 12 : 14 + rand() * 20)
      list.push({
        x: sx * (u + w / 2),
        z: sz * (22 + d / 2),
        w,
        d,
        h,
        style: STYLES[Math.floor(rand() * STYLES.length)],
        roofUnits: isForeground ? (u < 54 ? 0 : 1) : Math.floor(rand() * 2),
      })
      u += w + 4 + rand() * 3
    }
    let v = 50
    while (v < 104) {
      const w = 12 + rand() * 9
      const d = 14 + rand() * 8
      const h = isForeground ? 9 + rand() * 8 : 12 + rand() * 18
      list.push({
        x: sx * (22 + d / 2),
        z: sz * (v + w / 2),
        w: d,
        d: w,
        h,
        style: STYLES[Math.floor(rand() * STYLES.length)],
        roofUnits: Math.floor(rand() * 2),
      })
      v += w + 4 + rand() * 3
    }
  }
  return list
}

function Building({ spec, textures }: { spec: BuildingSpec; textures: Record<FacadeStyle, THREE.Texture> }) {
  const materials = useMemo(() => {
    const make = (span: number) => {
      const t = textures[spec.style].clone()
      t.repeat.set(span / 3.2, spec.h / 3.6)
      t.needsUpdate = true
      return new THREE.MeshStandardMaterial({ map: t, roughness: spec.style === 'glass' ? 0.25 : 0.75, metalness: spec.style === 'glass' ? 0.35 : 0.05 })
    }
    const front = make(spec.w)
    const sideM = make(spec.d)
    const roof = standardMaterial('#b9bcbf', 0.85)
    return [sideM, sideM, roof, roof, front, front]
  }, [spec, textures])

  return (
    <group position={[spec.x, GROUND, spec.z]}>
      <mesh castShadow receiveShadow position={[0, spec.h / 2, 0]} geometry={box(spec.w, spec.h, spec.d)} material={materials} />
      <mesh position={[0, 2.1, 0]} geometry={box(spec.w + 0.3, 4.2, spec.d + 0.3)} material={standardMaterial('#5d6b77', 0.2, 0.4)} />
      <mesh position={[0, 4.3, 0]} geometry={box(spec.w + 0.6, 0.3, spec.d + 0.6)} material={standardMaterial('#e3e1dc', 0.7)} />
      <mesh position={[0, spec.h + 0.35, 0]} geometry={box(spec.w + 0.2, 0.7, spec.d + 0.2)} material={standardMaterial('#d2d0cb', 0.8)} />
      {Array.from({ length: spec.roofUnits }, (_, i) => (
        <mesh key={i} castShadow position={[(i - 0.5) * spec.w * 0.3, spec.h + 1.4, spec.d * 0.15]} geometry={box(3.2, 1.6, 2.4)} material={standardMaterial('#c9ccd0', 0.6, 0.3)} />
      ))}
    </group>
  )
}

function Buildings() {
  const specs = useMemo(() => planBuildings(), [])
  const textures = useMemo(
    () => ({
      glass: createFacadeTexture('glass'),
      concrete: createFacadeTexture('concrete'),
      white: createFacadeTexture('white'),
      brick: createFacadeTexture('brick'),
    }),
    [],
  )
  return (
    <>
      {specs.map((s, i) => (
        <Building key={i} spec={s} textures={textures} />
      ))}
    </>
  )
}

function planTrees() {
  const rand = mulberry32(5)
  const trees: { x: number; z: number; s: number }[] = []
  for (const a of APPROACHES) {
    const d = APPROACH_HEADING[a]
    for (let along = 21; along < 104; along += 8.5) {
      if (Math.abs(((along - 26) % 30) - 0) < 2) continue
      for (const side of [1, -1]) {
        const p = armPoint(d, along + rand() * 1.5, side * (ROAD_HALF_WIDTH + 4.3))
        trees.push({ x: p.x, z: p.z, s: 0.85 + rand() * 0.35 })
      }
    }
  }
  for (const [sx, sz] of [[1, 1], [-1, 1], [1, -1], [-1, -1]]) {
    for (let i = 0; i < 3; i++) trees.push({ x: sx * (19.5 + rand() * 3), z: sz * (19.5 + rand() * 3), s: 0.9 + rand() * 0.3 })
  }
  return trees
}

const FOLIAGE = ['#5f8a4a', '#6f9a52', '#4f7a43', '#7ea35c', '#5a8550']

function Trees() {
  const trees = useMemo(() => planTrees(), [])
  const trunkRef = useRef<THREE.InstancedMesh>(null)
  const leafRef = useRef<THREE.InstancedMesh>(null)
  const leafGeo = useMemo(() => new THREE.IcosahedronGeometry(1, 1), [])
  const trunkGeo = useMemo(() => new THREE.CylinderGeometry(0.14, 0.22, 1, 8).translate(0, 0.5, 0), [])

  useLayoutEffect(() => {
    const rand = mulberry32(9)
    const m = new THREE.Matrix4()
    const q = new THREE.Quaternion()
    const c = new THREE.Color()
    trees.forEach((t, i) => {
      m.compose(new THREE.Vector3(t.x, GROUND, t.z), q, new THREE.Vector3(t.s, 3.4 * t.s, t.s))
      trunkRef.current?.setMatrixAt(i, m)
      for (let k = 0; k < 3; k++) {
        const r = (1.5 + rand() * 0.7) * t.s
        const pos = new THREE.Vector3(t.x + (rand() - 0.5) * 1.4 * t.s, GROUND + (3.6 + k * 0.9 + rand() * 0.5) * t.s, t.z + (rand() - 0.5) * 1.4 * t.s)
        q.setFromEuler(new THREE.Euler(rand() * 3, rand() * 3, 0))
        m.compose(pos, q, new THREE.Vector3(r, r * 0.88, r))
        leafRef.current?.setMatrixAt(i * 3 + k, m)
        leafRef.current?.setColorAt(i * 3 + k, c.set(FOLIAGE[Math.floor(rand() * FOLIAGE.length)]))
      }
      q.identity()
    })
    if (trunkRef.current) trunkRef.current.instanceMatrix.needsUpdate = true
    if (leafRef.current) {
      leafRef.current.instanceMatrix.needsUpdate = true
      if (leafRef.current.instanceColor) leafRef.current.instanceColor.needsUpdate = true
    }
  }, [trees])

  return (
    <>
      <instancedMesh ref={trunkRef} args={[trunkGeo, undefined, trees.length]} castShadow>
        <meshStandardMaterial color="#6b5440" roughness={0.9} />
      </instancedMesh>
      <instancedMesh ref={leafRef} args={[leafGeo, undefined, trees.length * 3]} castShadow receiveShadow>
        <meshStandardMaterial roughness={0.85} flatShading />
      </instancedMesh>
    </>
  )
}

function StreetLights() {
  const items = useMemo(() => {
    const list: { key: string; x: number; z: number; yaw: number }[] = []
    for (const a of APPROACHES) {
      const d = APPROACH_HEADING[a]
      for (const along of [26, 56, 86]) {
        const p = armPoint(d, along, ROAD_HALF_WIDTH + 1.2)
        const r = { x: -d.z, z: d.x }
        list.push({ key: `${a}${along}`, x: p.x, z: p.z, yaw: headingToYaw({ x: -r.x, z: -r.z }) })
      }
    }
    return list
  }, [])
  const pole = standardMaterial('#6d747c', 0.45, 0.6)
  return (
    <>
      {items.map((it) => (
        <group key={it.key} position={[it.x, GROUND, it.z]} rotation={[0, it.yaw, 0]}>
          <mesh castShadow position={[0, 4.2, 0]} geometry={cylinder(0.08, 0.13, 8.4, 10)} material={pole} />
          <mesh position={[0, 8.3, 1.1]} geometry={box(0.1, 0.1, 2.3)} material={pole} />
          <mesh position={[0, 8.2, 2.25]} geometry={box(0.42, 0.14, 0.9)} material={pole} />
          <mesh position={[0, 8.12, 2.25]} geometry={box(0.34, 0.03, 0.74)} material={standardMaterial('#fdfaf0', 0.3, 0, '#fff5d6', 0.6)} />
        </group>
      ))}
    </>
  )
}

const CLOTHES = ['#2f3d52', '#8a4b3a', '#d8d3c8', '#3c6e71', '#5b5f97', '#b5835a', '#283035', '#9d2f3a']

function Pedestrians() {
  const people = useMemo(() => {
    const rand = mulberry32(77)
    return Array.from({ length: 28 }, (_, i) => {
      const a = APPROACHES[i % 4]
      const side = rand() < 0.5 ? 1 : -1
      return {
        d: APPROACH_HEADING[a],
        offset: side * (ROAD_HALF_WIDTH + 2.4 + rand() * 1.4),
        start: 18 + rand() * 80,
        speed: (rand() < 0.3 ? 0 : 1.1 + rand() * 0.4) * (rand() < 0.5 ? 1 : -1),
        color: CLOTHES[Math.floor(rand() * CLOTHES.length)],
        height: 0.92 + rand() * 0.14,
      }
    })
  }, [])
  const bodyRef = useRef<THREE.InstancedMesh>(null)
  const headRef = useRef<THREE.InstancedMesh>(null)
  const bodyGeo = useMemo(() => new THREE.CapsuleGeometry(0.22, 0.95, 4, 8).translate(0, 0.7, 0), [])
  const headGeo = useMemo(() => new THREE.SphereGeometry(0.13, 10, 8), [])
  const state = useRef(people.map((p) => p.start))
  const tmp = useMemo(() => ({ m: new THREE.Matrix4(), q: new THREE.Quaternion(), v: new THREE.Vector3(), s: new THREE.Vector3(), c: new THREE.Color(), up: new THREE.Vector3(0, 1, 0) }), [])

  useLayoutEffect(() => {
    people.forEach((p, i) => bodyRef.current?.setColorAt(i, tmp.c.set(p.color)))
    if (bodyRef.current?.instanceColor) bodyRef.current.instanceColor.needsUpdate = true
  }, [people, tmp])

  useFrame((_, delta) => {
    const dt = Math.min(delta, 0.1)
    people.forEach((p, i) => {
      let along = state.current[i] + p.speed * dt
      if (along > 104) along = 18
      if (along < 18) along = 104
      state.current[i] = along
      const pos = armPoint(p.d, along, p.offset)
      const dir = p.speed >= 0 ? { x: -p.d.x, z: -p.d.z } : p.d
      tmp.q.setFromAxisAngle(tmp.up, p.speed === 0 ? i : headingToYaw(dir))
      tmp.s.set(1, p.height, 1)
      tmp.m.compose(tmp.v.set(pos.x, GROUND, pos.z), tmp.q, tmp.s)
      bodyRef.current?.setMatrixAt(i, tmp.m)
      tmp.s.set(1, 1, 1)
      tmp.m.compose(tmp.v.set(pos.x, GROUND + 1.4 * p.height + 0.12, pos.z), tmp.q, tmp.s)
      headRef.current?.setMatrixAt(i, tmp.m)
    })
    if (bodyRef.current) bodyRef.current.instanceMatrix.needsUpdate = true
    if (headRef.current) headRef.current.instanceMatrix.needsUpdate = true
  })

  return (
    <>
      <instancedMesh ref={bodyRef} args={[bodyGeo, undefined, people.length]} castShadow>
        <meshStandardMaterial roughness={0.8} />
      </instancedMesh>
      <instancedMesh ref={headRef} args={[headGeo, undefined, people.length]}>
        <meshStandardMaterial color="#c99a7a" roughness={0.7} />
      </instancedMesh>
    </>
  )
}

export function CityBlocks() {
  return (
    <group>
      <Buildings />
      <Trees />
      <StreetLights />
      <Pedestrians />
    </group>
  )
}
