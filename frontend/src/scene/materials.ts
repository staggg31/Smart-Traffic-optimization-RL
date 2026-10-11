import * as THREE from 'three'
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js'

/** Lazily-created caches so 50 vehicles share a handful of GPU resources. */

const paintCache = new Map<string, THREE.MeshPhysicalMaterial>()
export function paintMaterial(color: string) {
  let m = paintCache.get(color)
  if (!m) {
    m = new THREE.MeshPhysicalMaterial({
      color,
      metalness: 0.45,
      roughness: 0.32,
      clearcoat: 0.8,
      clearcoatRoughness: 0.18,
    })
    paintCache.set(color, m)
  }
  return m
}

const basicCache = new Map<string, THREE.MeshStandardMaterial>()
export function standardMaterial(color: string, roughness = 0.7, metalness = 0, emissive?: string, emissiveIntensity = 0) {
  const key = `${color}|${roughness}|${metalness}|${emissive ?? ''}|${emissiveIntensity}`
  let m = basicCache.get(key)
  if (!m) {
    m = new THREE.MeshStandardMaterial({ color, roughness, metalness })
    if (emissive) {
      m.emissive = new THREE.Color(emissive)
      m.emissiveIntensity = emissiveIntensity
    }
    basicCache.set(key, m)
  }
  return m
}

let glass: THREE.MeshPhysicalMaterial | null = null
export function glassMaterial() {
  if (!glass) {
    glass = new THREE.MeshPhysicalMaterial({
      color: '#1d2a36',
      metalness: 0.6,
      roughness: 0.08,
      clearcoat: 1,
      clearcoatRoughness: 0.05,
      envMapIntensity: 1.4,
    })
  }
  return glass
}

const roundedCache = new Map<string, RoundedBoxGeometry>()
export function roundedBox(w: number, h: number, d: number, r: number) {
  const key = `${w}|${h}|${d}|${r}`
  let g = roundedCache.get(key)
  if (!g) {
    g = new RoundedBoxGeometry(w, h, d, 3, Math.min(r, w / 2, h / 2, d / 2))
    roundedCache.set(key, g)
  }
  return g
}

const boxCache = new Map<string, THREE.BoxGeometry>()
export function box(w: number, h: number, d: number) {
  const key = `${w}|${h}|${d}`
  let g = boxCache.get(key)
  if (!g) {
    g = new THREE.BoxGeometry(w, h, d)
    boxCache.set(key, g)
  }
  return g
}

const cylCache = new Map<string, THREE.CylinderGeometry>()
export function cylinder(rTop: number, rBottom: number, h: number, segments = 20) {
  const key = `${rTop}|${rBottom}|${h}|${segments}`
  let g = cylCache.get(key)
  if (!g) {
    g = new THREE.CylinderGeometry(rTop, rBottom, h, segments)
    cylCache.set(key, g)
  }
  return g
}
