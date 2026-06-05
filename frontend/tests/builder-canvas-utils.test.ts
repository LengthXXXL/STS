import { describe, expect, it } from 'vitest'
import {
  dragOffsetFromPointer,
  screenToCanvasPoint,
  snapCanvasPoint,
  zoomTransformAtPoint,
  type CanvasRect,
  type CanvasTransform
} from '../src/utils/builderCanvas'

const rect: CanvasRect = {
  left: 100,
  top: 60,
  width: 800,
  height: 600
}

describe('builder canvas utilities', () => {
  it('converts screen coordinates into transformed canvas coordinates', () => {
    const transform: CanvasTransform = { x: 20, y: 10, scale: 2 }

    expect(screenToCanvasPoint(140, 100, rect, transform)).toEqual({ x: 10, y: 15 })
  })

  it('keeps the canvas point under the pointer stable while zooming', () => {
    const transform: CanvasTransform = { x: 30, y: -20, scale: 1 }
    const before = screenToCanvasPoint(300, 220, rect, transform)
    const zoomed = zoomTransformAtPoint(transform, rect, 300, 220, -100)
    const after = screenToCanvasPoint(300, 220, rect, zoomed)

    expect(zoomed.scale).toBeGreaterThan(transform.scale)
    expect(after.x).toBeCloseTo(before.x)
    expect(after.y).toBeCloseTo(before.y)
  })

  it('calculates drag offsets from pointer movement', () => {
    const offset = dragOffsetFromPointer(
      { x: 12, y: -8 },
      { clientX: 100, clientY: 120 },
      { clientX: 145, clientY: 90 }
    )

    expect(offset).toEqual({ x: 57, y: -38 })
  })

  it('snaps points to grid and nearby component positions when enabled', () => {
    const snapped = snapCanvasPoint(
      { x: 62, y: 97 },
      {
        enabled: true,
        targets: [{ id: 'a', x: 120, y: 96 }],
        movingId: 'b'
      }
    )

    expect(snapped).toEqual({ x: 72, y: 96 })
  })

  it('leaves points untouched when snapping is disabled', () => {
    const snapped = snapCanvasPoint(
      { x: 62, y: 97 },
      {
        enabled: false,
        targets: [{ id: 'a', x: 120, y: 96 }],
        movingId: 'b'
      }
    )

    expect(snapped).toEqual({ x: 62, y: 97 })
  })
})
