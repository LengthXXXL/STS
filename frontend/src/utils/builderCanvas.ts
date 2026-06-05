export interface CanvasTransform {
  x: number
  y: number
  scale: number
}

export interface CanvasRect {
  left: number
  top: number
  width: number
  height: number
}

interface PointerPoint {
  clientX: number
  clientY: number
}

export interface CanvasPoint {
  x: number
  y: number
}

export interface SnapTarget extends CanvasPoint {
  id: string
}

export interface SnapOptions {
  enabled: boolean
  targets?: SnapTarget[]
  movingId?: string
  gridSize?: number
  threshold?: number
}

const MIN_SCALE = 0.45
const MAX_SCALE = 2.4
const DEFAULT_GRID_SIZE = 24
const DEFAULT_SNAP_THRESHOLD = 14

export function clampScale(scale: number) {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale))
}

export function screenToCanvasPoint(
  clientX: number,
  clientY: number,
  rect: CanvasRect,
  transform: CanvasTransform
) {
  return {
    x: (clientX - rect.left - transform.x) / transform.scale,
    y: (clientY - rect.top - transform.y) / transform.scale
  }
}

export function zoomTransformAtPoint(
  transform: CanvasTransform,
  rect: CanvasRect,
  clientX: number,
  clientY: number,
  deltaY: number
): CanvasTransform {
  const nextScale = clampScale(transform.scale * Math.exp(-deltaY * 0.0018))
  const localX = clientX - rect.left
  const localY = clientY - rect.top
  const canvasX = (localX - transform.x) / transform.scale
  const canvasY = (localY - transform.y) / transform.scale

  return {
    x: localX - canvasX * nextScale,
    y: localY - canvasY * nextScale,
    scale: nextScale
  }
}

export function dragOffsetFromPointer(
  startOffset: { x: number; y: number },
  startPointer: PointerPoint,
  currentPointer: PointerPoint
) {
  return {
    x: startOffset.x + currentPointer.clientX - startPointer.clientX,
    y: startOffset.y + currentPointer.clientY - startPointer.clientY
  }
}

export function snapCanvasPoint(point: CanvasPoint, options: SnapOptions): CanvasPoint {
  if (!options.enabled) {
    return point
  }

  const gridSize = options.gridSize ?? DEFAULT_GRID_SIZE
  const threshold = options.threshold ?? DEFAULT_SNAP_THRESHOLD
  const snapped = {
    x: Math.round(point.x / gridSize) * gridSize,
    y: Math.round(point.y / gridSize) * gridSize
  }

  for (const target of options.targets ?? []) {
    if (target.id === options.movingId) {
      continue
    }

    if (Math.abs(point.x - target.x) <= threshold) {
      snapped.x = target.x
    }

    if (Math.abs(point.y - target.y) <= threshold) {
      snapped.y = target.y
    }
  }

  return snapped
}
