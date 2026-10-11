/**
 * Intersection layout + route geometry (pure TypeScript, no Three.js).
 *
 * World axes: +x = east, +z = south, +y = up. Right-hand traffic.
 * Every approach has three inbound lanes:
 *   lane 0 → protected left turn, lane 1 → through, lane 2 → through / right.
 */

export const LANE_WIDTH = 3.5
export const LANES_PER_DIRECTION = 3
export const ROAD_HALF_WIDTH = LANE_WIDTH * LANES_PER_DIRECTION
export const STOP_LINE_DISTANCE = 16.2
export const CROSSWALK_INNER = 11.6
export const CROSSWALK_OUTER = 15.0
export const SPAWN_DISTANCE = 96
export const WORLD_EXTENT = 110
export const CURB_CORNER_RADIUS = 4
export const SIDEWALK_HEIGHT = 0.16

export type ApproachId = 'N' | 'S' | 'E' | 'W'
export type Movement = 'left' | 'through' | 'right'
export type Vec2 = { x: number; z: number }

export const APPROACHES: ApproachId[] = ['N', 'S', 'E', 'W']

/** Travel heading of vehicles arriving FROM the given side. */
export const APPROACH_HEADING: Record<ApproachId, Vec2> = {
  N: { x: 0, z: 1 },
  S: { x: 0, z: -1 },
  E: { x: -1, z: 0 },
  W: { x: 1, z: 0 },
}

export const rightOf = (d: Vec2): Vec2 => ({ x: -d.z, z: d.x })
export const leftOf = (d: Vec2): Vec2 => ({ x: d.z, z: -d.x })
const add = (a: Vec2, b: Vec2): Vec2 => ({ x: a.x + b.x, z: a.z + b.z })
const scale = (a: Vec2, s: number): Vec2 => ({ x: a.x * s, z: a.z * s })
const dot = (a: Vec2, b: Vec2) => a.x * b.x + a.z * b.z

export const laneOffset = (lane: number) => LANE_WIDTH * (0.5 + lane)

/** Point on an arm: `along` = distance upstream from the centre, `offset` = distance to the driver's right. */
export function armPoint(d: Vec2, along: number, offset: number): Vec2 {
  return add(scale(d, -along), scale(rightOf(d), offset))
}

/** Rotation about +y that maps local +z onto heading d. */
export const headingToYaw = (d: Vec2) => Math.atan2(d.x, d.z)

export interface Route {
  approach: ApproachId
  lane: number
  movement: Movement
  points: Vec2[]
  cumulative: number[]
  length: number
  stopS: number
  curveStart: number
  curveEnd: number
  turnSpeed: number
}

function quadraticBezier(a: Vec2, c: Vec2, b: Vec2, steps: number): Vec2[] {
  const pts: Vec2[] = []
  for (let i = 1; i <= steps; i++) {
    const t = i / steps
    const mt = 1 - t
    pts.push({
      x: mt * mt * a.x + 2 * mt * t * c.x + t * t * b.x,
      z: mt * mt * a.z + 2 * mt * t * c.z + t * t * b.z,
    })
  }
  return pts
}

function densify(from: Vec2, to: Vec2, step = 2): Vec2[] {
  const dx = to.x - from.x
  const dz = to.z - from.z
  const len = Math.hypot(dx, dz)
  const n = Math.max(1, Math.ceil(len / step))
  const pts: Vec2[] = []
  for (let i = 1; i <= n; i++) pts.push({ x: from.x + (dx * i) / n, z: from.z + (dz * i) / n })
  return pts
}

function cumulativeLengths(points: Vec2[]) {
  const cum = [0]
  for (let i = 1; i < points.length; i++) {
    cum.push(cum[i - 1] + Math.hypot(points[i].x - points[i - 1].x, points[i].z - points[i - 1].z))
  }
  return cum
}

export function buildRoute(approach: ApproachId, lane: number, movement: Movement): Route {
  const d = APPROACH_HEADING[approach]
  const r = rightOf(d)
  const start = armPoint(d, SPAWN_DISTANCE, laneOffset(lane))

  if (movement === 'through') {
    const end = add(scale(d, SPAWN_DISTANCE), scale(r, laneOffset(lane)))
    const points = [start, ...densify(start, end)]
    const cumulative = cumulativeLengths(points)
    return {
      approach,
      lane,
      movement,
      points,
      cumulative,
      length: cumulative[cumulative.length - 1],
      stopS: SPAWN_DISTANCE - STOP_LINE_DISTANCE,
      curveStart: Infinity,
      curveEnd: Infinity,
      turnSpeed: 14,
    }
  }

  const outHeading = movement === 'left' ? leftOf(d) : rightOf(d)
  const outRight = rightOf(outHeading)
  const outLane = movement === 'left' ? 0 : LANES_PER_DIRECTION - 1
  const inset = movement === 'left' ? ROAD_HALF_WIDTH : ROAD_HALF_WIDTH + 3
  const entry = add(scale(d, -inset), scale(r, laneOffset(lane)))
  const exit = add(scale(outHeading, inset), scale(outRight, laneOffset(outLane)))
  const t = dot({ x: exit.x - entry.x, z: exit.z - entry.z }, d)
  const control = add(entry, scale(d, t))
  const end = add(scale(outHeading, SPAWN_DISTANCE), scale(outRight, laneOffset(outLane)))

  const approachPts = [start, ...densify(start, entry)]
  const curvePts = quadraticBezier(entry, control, exit, movement === 'left' ? 26 : 16)
  const exitPts = densify(exit, end)
  const points = [...approachPts, ...curvePts, ...exitPts]
  const cumulative = cumulativeLengths(points)
  const curveStart = cumulative[approachPts.length - 1]
  const curveEnd = cumulative[approachPts.length - 1 + curvePts.length]

  return {
    approach,
    lane,
    movement,
    points,
    cumulative,
    length: cumulative[cumulative.length - 1],
    stopS: SPAWN_DISTANCE - STOP_LINE_DISTANCE,
    curveStart,
    curveEnd,
    turnSpeed: movement === 'left' ? 7.5 : 4.8,
  }
}

/** Position + heading at arc length s. */
export function sampleRoute(route: Route, s: number, out: { x: number; z: number; yaw: number }) {
  const { points, cumulative } = route
  const clamped = Math.min(Math.max(s, 0), route.length)
  let lo = 0
  let hi = cumulative.length - 1
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1
    if (cumulative[mid] <= clamped) lo = mid
    else hi = mid
  }
  const segLen = cumulative[hi] - cumulative[lo] || 1
  const t = (clamped - cumulative[lo]) / segLen
  const a = points[lo]
  const b = points[hi]
  out.x = a.x + (b.x - a.x) * t
  out.z = a.z + (b.z - a.z) * t
  out.yaw = Math.atan2(b.x - a.x, b.z - a.z)
  return out
}
