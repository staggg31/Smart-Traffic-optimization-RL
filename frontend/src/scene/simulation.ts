/**
 * Illustrative frontend traffic animation.
 *
 * This is NOT SUMO and NOT the trained PPO policy. It is a lightweight
 * car-following (IDM) + signal-phase demo used to animate the 3D scene.
 * Replace it with SUMO TraCI telemetry (vehicle positions + signal states)
 * once a backend bridge exists — see README "Connecting real telemetry".
 */
import type { ControllerId, SafetyConstraints, SceneEvent, ScenarioDemand } from '../types'
import {
  APPROACHES,
  type ApproachId,
  type Movement,
  type Route,
  buildRoute,
  sampleRoute,
} from './layout'

export type VehicleKind = 'sedan' | 'suv' | 'taxi' | 'truck' | 'bus'
export type SignalColor = 'green' | 'yellow' | 'red'
export type PhaseId = 'NS_T' | 'NS_L' | 'EW_T' | 'EW_L'
type Stage = 'green' | 'yellow' | 'allred'

export const PHASES: PhaseId[] = ['NS_T', 'NS_L', 'EW_T', 'EW_L']
export const PHASE_LABEL: Record<PhaseId, string> = {
  NS_T: 'NS Through',
  NS_L: 'NS Left',
  EW_T: 'EW Through',
  EW_L: 'EW Left',
}

const VEHICLE_SPECS: Record<VehicleKind, { length: number; v0: number; accel: number }> = {
  sedan: { length: 4.6, v0: 13.5, accel: 1.8 },
  suv: { length: 4.9, v0: 13, accel: 1.6 },
  taxi: { length: 4.6, v0: 13.5, accel: 1.9 },
  truck: { length: 6.8, v0: 11, accel: 1.1 },
  bus: { length: 12, v0: 10.5, accel: 0.9 },
}

const CAR_COLORS = ['#e9ecef', '#c4c9cf', '#9aa2ab', '#4b525a', '#2d3238', '#1f4e8c', '#2c6fb3', '#b3262e', '#7d1f24', '#3d5a45', '#d8d2c4', '#5b6d82']
const MAX_VEHICLES = 52
const IDM_B = 3.2
const IDM_S0 = 2.4
const IDM_T = 1.25

export interface SimVehicle {
  id: number
  kind: VehicleKind
  color: string
  route: Route
  s: number
  v: number
  acc: number
  length: number
  v0: number
  accel: number
  passedStop: boolean
  enteredBox: boolean
  wheelAngle: number
  x: number
  z: number
  yaw: number
}

export function mulberry32(seed: number) {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const phaseOf = (approach: ApproachId, lane: number): PhaseId => {
  const axis = approach === 'N' || approach === 'S' ? 'NS' : 'EW'
  return `${axis}_${lane === 0 ? 'L' : 'T'}` as PhaseId
}

const formatClock = (t: number) => {
  const m = Math.floor(t / 60)
  const s = Math.floor(t % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

export interface SimulationOptions {
  seed: number
  demand: ScenarioDemand
  controller: ControllerId
  constraints: SafetyConstraints
}

export class TrafficSimulation {
  time = 0
  vehicles: SimVehicle[] = []
  phaseIndex = 0
  stage: Stage = 'green'
  stageElapsed = 0
  greenDuration: number
  completed = 0
  violations = 0
  controller: ControllerId
  onEvent?: (e: SceneEvent) => void
  onRosterChange?: () => void

  private rng: () => number
  private demand: ScenarioDemand
  private constraints: SafetyConstraints
  private nextId = 1
  private spawnTimers = new Map<string, number>()
  private routes = new Map<string, Route>()
  private gapTimer = 0
  private eventId = 0
  private readonly scratch = { x: 0, z: 0, yaw: 0 }

  constructor(opts: SimulationOptions) {
    this.rng = mulberry32(opts.seed)
    this.demand = opts.demand
    this.controller = opts.controller
    this.constraints = opts.constraints
    this.greenDuration = this.fixedGreen(PHASES[0])
    for (const a of APPROACHES) {
      for (let lane = 0; lane < 3; lane++) this.spawnTimers.set(`${a}${lane}`, this.rng() * 4)
    }
    this.prefill()
  }

  get phase(): PhaseId {
    return PHASES[this.phaseIndex]
  }

  setController(controller: ControllerId) {
    if (controller === this.controller) return
    this.controller = controller
    this.emit(`Controller switched to ${controller === 'ppo' ? 'adaptive stand-in' : controller}`, 'info')
  }

  signalFor(approach: ApproachId, lane: number): SignalColor {
    if (phaseOf(approach, lane) !== this.phase || this.stage === 'allred') return 'red'
    return this.stage === 'green' ? 'green' : 'yellow'
  }

  queuedCount() {
    let n = 0
    for (const v of this.vehicles) if (!v.passedStop && v.v < 0.6 && v.s > v.route.stopS - 80) n++
    return n
  }

  step(dt: number) {
    let remaining = Math.min(dt, 0.25)
    while (remaining > 1e-6) {
      const h = Math.min(remaining, 1 / 30)
      this.tick(h)
      remaining -= h
    }
  }

  private route(approach: ApproachId, lane: number, movement: Movement) {
    const key = `${approach}${lane}${movement}`
    let r = this.routes.get(key)
    if (!r) {
      r = buildRoute(approach, lane, movement)
      this.routes.set(key, r)
    }
    return r
  }

  private emit(text: string, tone: SceneEvent['tone']) {
    this.onEvent?.({ id: ++this.eventId, time: formatClock(this.time), text, tone })
  }

  private prefill() {
    for (const a of APPROACHES) {
      for (let lane = 0; lane < 3; lane++) {
        const count = 1 + Math.floor(this.rng() * 3)
        for (let i = 0; i < count; i++) {
          const v = this.createVehicle(a, lane)
          v.s = v.route.stopS - 6 - i * (v.length + 3.4) - this.rng() * 1.5
          v.v = 0
          if (v.s > 0) this.vehicles.push(v)
        }
      }
    }
  }

  private createVehicle(approach: ApproachId, lane: number): SimVehicle {
    const r = this.rng()
    let kind: VehicleKind
    if (lane === 0) kind = r < 0.55 ? 'sedan' : r < 0.85 ? 'suv' : 'taxi'
    else kind = r < 0.4 ? 'sedan' : r < 0.62 ? 'suv' : r < 0.74 ? 'taxi' : r < 0.87 ? 'truck' : 'bus'

    let movement: Movement = 'through'
    if (lane === 0) movement = 'left'
    else if (lane === 2 && this.rng() < 0.35) movement = 'right'

    const spec = VEHICLE_SPECS[kind]
    const color =
      kind === 'taxi' ? '#f2b705' : kind === 'bus' ? '#2563c9' : kind === 'truck' ? '#f1f2f0' : CAR_COLORS[Math.floor(this.rng() * CAR_COLORS.length)]
    const route = this.route(approach, lane, movement)
    return {
      id: this.nextId++,
      kind,
      color,
      route,
      s: 0,
      v: spec.v0 * 0.8,
      acc: 0,
      length: spec.length,
      v0: spec.v0 * (0.9 + this.rng() * 0.15),
      accel: spec.accel,
      passedStop: false,
      enteredBox: false,
      wheelAngle: this.rng() * Math.PI * 2,
      x: 0,
      z: 0,
      yaw: 0,
    }
  }

  private tick(dt: number) {
    this.time += dt
    this.updateSignals(dt)
    this.spawn(dt)
    this.updatePositions()
    this.updateVehicles(dt)
  }

  private fixedGreen(p: PhaseId) {
    return p.endsWith('L') ? 9 : 22
  }

  private demandOn(p: PhaseId, radius = 80) {
    let queue = 0
    for (const v of this.vehicles) {
      if (v.passedStop) continue
      if (phaseOf(v.route.approach, v.route.lane) !== p) continue
      if (v.route.stopS - v.s < radius) queue++
    }
    return queue
  }

  private updateSignals(dt: number) {
    const { minGreen, yellow, allRed, maxGreen } = this.constraints
    this.stageElapsed += dt

    if (this.stage === 'green') {
      let end = this.stageElapsed >= this.greenDuration
      if (this.controller === 'actuated' && this.stageElapsed >= minGreen) {
        const detected = this.demandOn(this.phase, 32) > 0
        this.gapTimer = detected ? 0 : this.gapTimer + dt
        end = this.gapTimer > 2.5 || this.stageElapsed >= maxGreen
      }
      if (end) {
        if (this.stageElapsed + 1e-3 < minGreen || this.stageElapsed > maxGreen + 0.5) this.violations++
        this.stage = 'yellow'
        this.stageElapsed = 0
        this.emit(`${PHASE_LABEL[this.phase]} → yellow`, 'phase')
      }
    } else if (this.stage === 'yellow') {
      if (this.stageElapsed >= yellow) {
        this.stage = 'allred'
        this.stageElapsed = 0
      }
    } else if (this.stageElapsed >= allRed) {
      this.phaseIndex = this.pickNextPhase()
      this.stage = 'green'
      this.stageElapsed = 0
      this.gapTimer = 0
      this.greenDuration = this.planGreen(this.phase)
      this.emit(`Signal phase changed (${PHASE_LABEL[this.phase]} green)`, 'phase')
    }
  }

  private pickNextPhase() {
    if (this.controller === 'fixed') return (this.phaseIndex + 1) % PHASES.length
    if (this.controller === 'actuated') {
      for (let i = 1; i <= PHASES.length; i++) {
        const idx = (this.phaseIndex + i) % PHASES.length
        if (!PHASES[idx].endsWith('L') || this.demandOn(PHASES[idx], 40) > 0) return idx
      }
      return (this.phaseIndex + 1) % PHASES.length
    }
    // Adaptive stand-in: serve the most pressured phase (never the one just served).
    let best = (this.phaseIndex + 1) % PHASES.length
    let bestScore = -1
    for (let i = 1; i < PHASES.length; i++) {
      const idx = (this.phaseIndex + i) % PHASES.length
      const score = this.demandOn(PHASES[idx]) + i * 0.01
      if (score > bestScore) {
        bestScore = score
        best = idx
      }
    }
    return best
  }

  private planGreen(p: PhaseId) {
    const { minGreen, maxGreen } = this.constraints
    if (this.controller === 'fixed') return Math.min(Math.max(this.fixedGreen(p), minGreen), maxGreen)
    if (this.controller === 'actuated') return maxGreen
    return Math.min(Math.max(minGreen + this.demandOn(p) * 2.1, minGreen), maxGreen)
  }

  private spawn(dt: number) {
    let changed = false
    for (const a of APPROACHES) {
      const rate = a === 'N' || a === 'S' ? this.demand.ns : this.demand.ew
      for (let lane = 0; lane < 3; lane++) {
        const key = `${a}${lane}`
        const t = (this.spawnTimers.get(key) ?? 0) - dt
        if (t > 0) {
          this.spawnTimers.set(key, t)
          continue
        }
        const laneRate = lane === 0 ? rate * 0.55 : rate
        const blocked = this.vehicles.some((v) => v.route.approach === a && v.route.lane === lane && v.s < 16)
        if (!blocked && this.vehicles.length < MAX_VEHICLES) {
          this.vehicles.push(this.createVehicle(a, lane))
          changed = true
          this.spawnTimers.set(key, -Math.log(1 - this.rng()) / laneRate + 1.2)
        } else {
          this.spawnTimers.set(key, 0.6)
        }
      }
    }

    const before = this.vehicles.length
    this.vehicles = this.vehicles.filter((v) => {
      if (v.s < v.route.length - 1) return true
      this.completed++
      return false
    })
    if (changed || before !== this.vehicles.length) this.onRosterChange?.()
  }

  private updatePositions() {
    for (const v of this.vehicles) {
      sampleRoute(v.route, v.s, this.scratch)
      v.x = this.scratch.x
      v.z = this.scratch.z
      v.yaw = this.scratch.yaw
    }
  }

  private updateVehicles(dt: number) {
    const list = this.vehicles
    for (const me of list) {
      const hx = Math.sin(me.yaw)
      const hz = Math.cos(me.yaw)
      let gap = Infinity
      let leaderV = me.v

      for (const other of list) {
        if (other === me) continue
        const dx = other.x - me.x
        const dz = other.z - me.z
        const along = dx * hx + dz * hz
        if (along <= 0 || along > 45) continue
        const lateral = Math.abs(dx * hz - dz * hx)
        const sameDirection = Math.sin(other.yaw) * hx + Math.cos(other.yaw) * hz > 0.35
        const conflict = sameDirection ? lateral < 2.1 : lateral < 1.6 && along < 9
        if (!conflict) continue
        const g = along - (me.length + other.length) / 2
        if (g < gap) {
          gap = g
          leaderV = sameDirection ? other.v : 0
        }
      }

      if (!me.passedStop) {
        const front = me.s + me.length / 2
        const toStop = me.route.stopS - front
        const signal = this.signalFor(me.route.approach, me.route.lane)
        const mustStop = signal === 'red' || (signal === 'yellow' && toStop > (me.v * me.v) / (2 * 4.2) + 0.5)
        if (mustStop && toStop > -0.5 && toStop < gap) {
          gap = Math.max(toStop, 0.05)
          leaderV = 0
        }
        if (toStop < -0.5) {
          me.passedStop = true
        }
      }

      let v0 = me.v0
      const { curveStart, curveEnd, turnSpeed } = me.route
      if (me.s >= curveStart - me.length / 2 && me.s <= curveEnd) v0 = Math.min(v0, turnSpeed)
      else if (me.s < curveStart) v0 = Math.min(v0, Math.sqrt(turnSpeed * turnSpeed + 2 * 1.6 * (curveStart - me.s)))

      const dv = me.v - leaderV
      const sStar = IDM_S0 + Math.max(0, me.v * IDM_T + (me.v * dv) / (2 * Math.sqrt(me.accel * IDM_B)))
      const free = 1 - Math.pow(me.v / Math.max(v0, 0.1), 4)
      const interaction = gap === Infinity ? 0 : Math.pow(sStar / Math.max(gap, 0.1), 2)
      me.acc = Math.max(-9, Math.min(me.accel, me.accel * (free - interaction)))
    }

    for (const me of list) {
      me.v = Math.max(0, me.v + me.acc * dt)
      const ds = me.v * dt
      me.s += ds
      me.wheelAngle += ds / (me.kind === 'bus' ? 0.5 : me.kind === 'truck' ? 0.45 : 0.35)
      if (!me.enteredBox && me.passedStop && me.s > me.route.stopS + 4) {
        me.enteredBox = true
        if (me.kind === 'bus') this.emit('Bus entered intersection', 'vehicle')
      }
    }
  }
}
