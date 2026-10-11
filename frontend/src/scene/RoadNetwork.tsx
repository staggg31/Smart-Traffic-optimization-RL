/**
 * RoadNetwork Component
 *
 * Renders the accurate physical intersection geometry matching `single_intersection.net.xml`:
 * - 4 Orthogonal Approaches (North, South, East, West)
 * - 8 Incoming Lanes (2 lanes per approach: lane 0 inner, lane 1 outer)
 * - 8 Outgoing Lanes (2 departure lanes per approach)
 * - Stop Bars located at `STOP_LINE_DISTANCE = 18m` from intersection center
 * - Crosswalk markings with zebra striping at approach mouths
 * - High-grip procedural asphalt, concrete curbs, and sidewalk textures
 */

import { useLayoutEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import {
  APPROACHES,
  APPROACH_HEADING,
  CROSSWALK_INNER,
  CROSSWALK_OUTER,
  CURB_CORNER_RADIUS,
  LANE_WIDTH,
  ROAD_HALF_WIDTH,
  SIDEWALK_HEIGHT,
  STOP_LINE_DISTANCE,
  WORLD_EXTENT,
  type Vec2,
  armPoint,
  headingToYaw,
  laneOffset,
} from './layout'
import { createAsphaltTexture, createGrassTexture, createPavingTexture } from './textures'

type Rect = { x: number; z: number; yaw: number; width: number; length: number }

const MARK_Y = 0.015

function rectOnArm(d: Vec2, alongFrom: number, alongTo: number, offset: number, width: number): Rect {
  const mid = (alongFrom + alongTo) / 2
  const p = armPoint(d, mid, offset)
  return { x: p.x, z: p.z, yaw: headingToYaw(d), width, length: Math.abs(alongTo - alongFrom) }
}

function dashed(d: Vec2, from: number, to: number, offset: number, dash = 3, gap = 6, width = 0.14) {
  const out: Rect[] = []
  for (let a = from; a + dash <= to; a += dash + gap) out.push(rectOnArm(d, a, a + dash, offset, width))
  return out
}

function buildMarkings() {
  const white: Rect[] = []
  const yellow: Rect[] = []
  const far = WORLD_EXTENT
  for (const a of APPROACHES) {
    const d = APPROACH_HEADING[a]
    yellow.push(rectOnArm(d, STOP_LINE_DISTANCE, far, 0.16, 0.13), rectOnArm(d, STOP_LINE_DISTANCE, far, -0.16, 0.13))
    for (const off of [LANE_WIDTH, LANE_WIDTH * 2]) {
      white.push(rectOnArm(d, STOP_LINE_DISTANCE, 34, off, 0.14))
      white.push(...dashed(d, 34, far, off))
      white.push(...dashed(d, CROSSWALK_OUTER + 0.6, far, -off))
    }
    white.push(rectOnArm(d, CROSSWALK_OUTER + 0.4, far, ROAD_HALF_WIDTH - 0.3, 0.16))
    white.push(rectOnArm(d, CROSSWALK_OUTER + 0.4, far, -(ROAD_HALF_WIDTH - 0.3), 0.16))
    white.push({ ...rectOnArm(d, STOP_LINE_DISTANCE - 0.25, STOP_LINE_DISTANCE + 0.25, ROAD_HALF_WIDTH / 2 + 0.15, ROAD_HALF_WIDTH - 0.5) })
    for (let off = -ROAD_HALF_WIDTH + 0.7; off <= ROAD_HALF_WIDTH - 0.6; off += 1.2) {
      white.push(rectOnArm(d, CROSSWALK_INNER, CROSSWALK_OUTER, off, 0.6))
    }
  }
  return { white, yellow }
}

function MarkingInstances({ rects, color }: { rects: Rect[]; color: string }) {
  const ref = useRef<THREE.InstancedMesh>(null)
  const geometry = useMemo(() => new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2), [])
  useLayoutEffect(() => {
    const mesh = ref.current
    if (!mesh) return
    const m = new THREE.Matrix4()
    const q = new THREE.Quaternion()
    const up = new THREE.Vector3(0, 1, 0)
    rects.forEach((r, i) => {
      q.setFromAxisAngle(up, r.yaw)
      m.compose(new THREE.Vector3(r.x, MARK_Y, r.z), q, new THREE.Vector3(r.width, 1, r.length))
      mesh.setMatrixAt(i, m)
    })
    mesh.instanceMatrix.needsUpdate = true
  }, [rects])
  return (
    <instancedMesh ref={ref} args={[geometry, undefined, rects.length]} receiveShadow>
      <meshStandardMaterial color={color} roughness={0.85} polygonOffset polygonOffsetFactor={-2} />
    </instancedMesh>
  )
}

function arrowShapes() {
  const shape = (pts: [number, number][]) => new THREE.Shape(pts.map(([x, y]) => new THREE.Vector2(x, y)))
  const straight = shape([[-0.15, 0], [0.15, 0], [0.15, 3.2], [0.55, 3.2], [0, 4.6], [-0.55, 3.2], [-0.15, 3.2]])
  const leftPts: [number, number][] = [[-0.15, 0], [0.15, 0], [0.15, 2.9], [-0.9, 2.9], [-0.9, 3.35], [-1.7, 2.75], [-0.9, 2.15], [-0.9, 2.6], [-0.15, 2.6]]
  const left = shape(leftPts)
  const right = shape(leftPts.map(([x, y]) => [-x, y] as [number, number]).reverse())
  return {
    straight: new THREE.ShapeGeometry(straight).rotateX(-Math.PI / 2),
    left: new THREE.ShapeGeometry(left).rotateX(-Math.PI / 2),
    right: new THREE.ShapeGeometry(right).rotateX(-Math.PI / 2),
  }
}

function LaneArrows() {
  const geos = useMemo(() => arrowShapes(), [])
  const material = useMemo(() => new THREE.MeshStandardMaterial({ color: '#f2f2ee', roughness: 0.85, polygonOffset: true, polygonOffsetFactor: -2 }), [])
  const items = useMemo(() => {
    const list: { key: string; x: number; z: number; yaw: number; geo: THREE.BufferGeometry }[] = []
    for (const a of APPROACHES) {
      const d = APPROACH_HEADING[a]
      const yaw = Math.atan2(-d.x, -d.z)
      for (const along of [STOP_LINE_DISTANCE + 6.5, STOP_LINE_DISTANCE + 24]) {
        const geoByLane = [[geos.left], [geos.straight], [geos.straight, geos.right]]
        geoByLane.forEach((gs, lane) => {
          const p = armPoint(d, along, laneOffset(lane))
          gs.forEach((geo, gi) => list.push({ key: `${a}-${along}-${lane}-${gi}`, x: p.x, z: p.z, yaw, geo }))
        })
      }
    }
    return list
  }, [geos])
  return (
    <>
      {items.map((it) => (
        <mesh key={it.key} geometry={it.geo} material={material} position={[it.x, MARK_Y, it.z]} rotation={[0, it.yaw, 0]} receiveShadow />
      ))}
    </>
  )
}

function quadrantShape(sx: number, sz: number) {
  const R = ROAD_HALF_WIDTH
  const F = WORLD_EXTENT
  const cr = CURB_CORNER_RADIUS
  const local: [number, number][] = [[R + cr, R], [F, R], [F, F], [R, F], [R, R + cr]]
  for (let i = 1; i < 10; i++) {
    const t = Math.PI + (i / 10) * (Math.PI / 2)
    local.push([R + cr + Math.cos(t) * cr, R + cr + Math.sin(t) * cr])
  }
  return new THREE.Shape(local.map(([u, v]) => new THREE.Vector2(sx * u, -sz * v)))
}

function Sidewalks() {
  const { geometries, top, side } = useMemo(() => {
    const paving = createPavingTexture()
    paving.repeat.set(0.25, 0.25)
    const g = [
      [1, 1],
      [-1, 1],
      [1, -1],
      [-1, -1],
    ].map(([sx, sz]) => new THREE.ExtrudeGeometry(quadrantShape(sx, sz), { depth: SIDEWALK_HEIGHT, bevelEnabled: false }).rotateX(-Math.PI / 2))
    return {
      geometries: g,
      top: new THREE.MeshStandardMaterial({ map: paving, roughness: 0.9 }),
      side: new THREE.MeshStandardMaterial({ color: '#b9b6ae', roughness: 0.8 }),
    }
  }, [])
  return (
    <>
      {geometries.map((g, i) => (
        <mesh key={i} geometry={g} material={[top, side]} receiveShadow />
      ))}
    </>
  )
}

export function RoadNetwork() {
  const { white, yellow } = useMemo(() => buildMarkings(), [])
  const asphalt = useMemo(() => {
    const t = createAsphaltTexture()
    t.repeat.set(ROAD_HALF_WIDTH / 6, (WORLD_EXTENT * 2) / 6)
    return t
  }, [])
  const asphaltEW = useMemo(() => {
    const t = asphalt.clone()
    t.repeat.set(ROAD_HALF_WIDTH / 6, (WORLD_EXTENT - ROAD_HALF_WIDTH) / 12)
    return t
  }, [asphalt])
  const grass = useMemo(() => {
    const t = createGrassTexture()
    t.repeat.set(60, 60)
    return t
  }, [])
  const armLength = WORLD_EXTENT - ROAD_HALF_WIDTH

  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.02, 0]} receiveShadow>
        <planeGeometry args={[700, 700]} />
        <meshStandardMaterial map={grass} color="#c8d1bf" roughness={1} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
        <planeGeometry args={[ROAD_HALF_WIDTH * 2, WORLD_EXTENT * 2]} />
        <meshStandardMaterial map={asphalt} roughness={0.92} />
      </mesh>
      {[1, -1].map((s) => (
        <mesh key={s} rotation={[-Math.PI / 2, 0, Math.PI / 2]} position={[s * (ROAD_HALF_WIDTH + armLength / 2), 0, 0]} receiveShadow>
          <planeGeometry args={[ROAD_HALF_WIDTH * 2, armLength]} />
          <meshStandardMaterial map={asphaltEW} roughness={0.92} />
        </mesh>
      ))}
      <Sidewalks />
      <MarkingInstances rects={white} color="#f1f1ec" />
      <MarkingInstances rects={yellow} color="#e8b630" />
      <LaneArrows />
    </group>
  )
}
