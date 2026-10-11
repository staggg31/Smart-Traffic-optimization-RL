import * as THREE from 'three'
import { mulberry32 } from './simulation'

/** Procedural canvas textures — no external image assets required. */

function canvas(size: number) {
  const c = document.createElement('canvas')
  c.width = size
  c.height = size
  const ctx = c.getContext('2d')
  if (!ctx) throw new Error('2D canvas unavailable')
  return { c, ctx }
}

function finish(c: HTMLCanvasElement, repeat = 1, srgb = true) {
  const tex = new THREE.CanvasTexture(c)
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping
  tex.repeat.set(repeat, repeat)
  tex.anisotropy = 4
  if (srgb) tex.colorSpace = THREE.SRGBColorSpace
  return tex
}

export function createAsphaltTexture() {
  const { c, ctx } = canvas(512)
  const rand = mulberry32(7)
  ctx.fillStyle = '#4a4e54'
  ctx.fillRect(0, 0, 512, 512)
  for (let i = 0; i < 26000; i++) {
    const v = 58 + Math.floor(rand() * 40)
    ctx.fillStyle = `rgba(${v},${v + 2},${v + 6},${0.25 + rand() * 0.35})`
    ctx.fillRect(rand() * 512, rand() * 512, 1 + rand() * 1.6, 1 + rand() * 1.6)
  }
  for (let i = 0; i < 18; i++) {
    ctx.fillStyle = `rgba(30,32,36,${0.05 + rand() * 0.06})`
    ctx.beginPath()
    ctx.ellipse(rand() * 512, rand() * 512, 20 + rand() * 70, 10 + rand() * 40, rand() * Math.PI, 0, Math.PI * 2)
    ctx.fill()
  }
  return finish(c, 1)
}

export function createPavingTexture() {
  const { c, ctx } = canvas(256)
  const rand = mulberry32(11)
  ctx.fillStyle = '#c9c6bf'
  ctx.fillRect(0, 0, 256, 256)
  const tile = 32
  for (let y = 0; y < 256; y += tile) {
    for (let x = 0; x < 256; x += tile) {
      const v = 196 + Math.floor(rand() * 22)
      ctx.fillStyle = `rgb(${v},${v - 3},${v - 9})`
      ctx.fillRect(x + 1, y + 1, tile - 2, tile - 2)
    }
  }
  ctx.strokeStyle = 'rgba(120,115,105,0.35)'
  ctx.lineWidth = 1.5
  for (let i = 0; i <= 256; i += tile) {
    ctx.beginPath()
    ctx.moveTo(i, 0)
    ctx.lineTo(i, 256)
    ctx.moveTo(0, i)
    ctx.lineTo(256, i)
    ctx.stroke()
  }
  return finish(c, 1)
}

export function createGrassTexture() {
  const { c, ctx } = canvas(256)
  const rand = mulberry32(19)
  ctx.fillStyle = '#7f9a62'
  ctx.fillRect(0, 0, 256, 256)
  for (let i = 0; i < 9000; i++) {
    const g = 120 + Math.floor(rand() * 50)
    ctx.fillStyle = `rgba(${g - 40},${g},${g - 70},0.5)`
    ctx.fillRect(rand() * 256, rand() * 256, 1.5, 2.5)
  }
  return finish(c, 1)
}

export type FacadeStyle = 'glass' | 'concrete' | 'brick' | 'white'

const FACADE_COLORS: Record<FacadeStyle, { wall: string; glass: string; frame: string }> = {
  glass: { wall: '#8ea5b8', glass: '#5d7d98', frame: '#d7dee5' },
  concrete: { wall: '#d9d4ca', glass: '#5a6f82', frame: '#b8b1a5' },
  brick: { wall: '#a8735a', glass: '#4f6274', frame: '#e7dccd' },
  white: { wall: '#eef0f1', glass: '#6c8aa3', frame: '#c9cfd4' },
}

/** One bay (≈3 m wide × 3.6 m storey) — tiled across a facade via texture.repeat. */
export function createFacadeTexture(style: FacadeStyle) {
  const { c, ctx } = canvas(128)
  const col = FACADE_COLORS[style]
  ctx.fillStyle = col.wall
  ctx.fillRect(0, 0, 128, 128)
  const grad = ctx.createLinearGradient(0, 0, 128, 128)
  grad.addColorStop(0, col.glass)
  grad.addColorStop(0.55, '#9fb6c9')
  grad.addColorStop(1, col.glass)
  ctx.fillStyle = grad
  if (style === 'glass') {
    ctx.fillRect(6, 8, 116, 104)
    ctx.fillStyle = col.frame
    ctx.fillRect(62, 8, 4, 104)
    ctx.fillRect(0, 112, 128, 16)
  } else {
    ctx.fillRect(22, 26, 84, 66)
    ctx.fillStyle = col.frame
    ctx.fillRect(18, 92, 92, 8)
    ctx.fillRect(62, 26, 4, 66)
  }
  ctx.fillStyle = 'rgba(255,255,255,0.18)'
  ctx.beginPath()
  ctx.moveTo(style === 'glass' ? 8 : 24, style === 'glass' ? 10 : 28)
  ctx.lineTo(54, style === 'glass' ? 10 : 28)
  ctx.lineTo(24, 80)
  ctx.closePath()
  ctx.fill()
  return finish(c, 1)
}
