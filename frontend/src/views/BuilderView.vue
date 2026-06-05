<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import {
  dragOffsetFromPointer,
  screenToCanvasPoint,
  zoomTransformAtPoint,
  type CanvasRect,
  type CanvasTransform
} from '../utils/builderCanvas'

interface BlockDefinition {
  id: string
  label: string
  category: string
  tone: 'action' | 'risk' | 'condition'
}

interface PlacedBlock {
  id: string
  blockId: string
  label: string
  tone: BlockDefinition['tone']
  x: number
  y: number
}

interface DragState {
  startPointer: { clientX: number; clientY: number }
  startOffset: { x: number; y: number }
}

const blockDefinitions: BlockDefinition[] = [
  { id: 'buy', label: '买入', category: '动作', tone: 'action' },
  { id: 'sell', label: '卖出', category: '动作', tone: 'action' },
  { id: 'clear', label: '清仓', category: '动作', tone: 'action' },
  { id: 'take-profit', label: '止盈', category: '风控', tone: 'risk' },
  { id: 'stop-loss', label: '止损', category: '风控', tone: 'risk' },
  { id: 'cooldown', label: '冷却', category: '风控', tone: 'condition' }
]

const canvasRef = ref<HTMLElement | null>(null)
const transform = reactive<CanvasTransform>({ x: 0, y: 0, scale: 1 })
const libraryOffset = reactive({ x: 0, y: 0 })
const placedBlocks = ref<PlacedBlock[]>([])
const draggingBlock = ref<{ block: BlockDefinition; x: number; y: number } | null>(null)
const isPanning = ref(false)
const isDraggingLibrary = ref(false)

let panState: DragState | null = null
let libraryDragState: DragState | null = null
let blockDragState: { block: BlockDefinition; pointerId: number | null } | null = null

const canvasStyle = computed(() => ({
  '--grid-size': `${24 * transform.scale}px`,
  '--grid-x': `${transform.x}px`,
  '--grid-y': `${transform.y}px`
}))

const worldStyle = computed(() => ({
  transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})`
}))

const libraryStyle = computed(() => ({
  transform: `translate(${libraryOffset.x}px, ${libraryOffset.y}px)`
}))

const zoomLabel = computed(() => `${Math.round(transform.scale * 100)}%`)

function toCanvasRect(rect: DOMRect): CanvasRect {
  return {
    left: rect.left,
    top: rect.top,
    width: rect.width,
    height: rect.height
  }
}

function startBlockDrag(block: BlockDefinition, event: DragEvent) {
  event.dataTransfer?.setData('application/sts-block', block.id)
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'copy'
  }
}

function beginBlockDrag(
  block: BlockDefinition,
  clientX: number,
  clientY: number,
  pointerId: number | null
) {
  blockDragState = { block, pointerId }
  draggingBlock.value = { block, x: clientX, y: clientY }
}

function updateBlockDrag(clientX: number, clientY: number) {
  if (!blockDragState) {
    return
  }

  draggingBlock.value = {
    block: blockDragState.block,
    x: clientX,
    y: clientY
  }
}

function finishBlockDrag(clientX: number, clientY: number) {
  if (!blockDragState) {
    return
  }

  addBlockAtClientPoint(blockDragState.block, clientX, clientY)
  draggingBlock.value = null
  blockDragState = null
}

function addBlockAtClientPoint(block: BlockDefinition, clientX: number, clientY: number) {
  const rect = canvasRef.value?.getBoundingClientRect()
  if (
    !rect ||
    clientX < rect.left ||
    clientX > rect.right ||
    clientY < rect.top ||
    clientY > rect.bottom
  ) {
    return
  }

  const point = screenToCanvasPoint(clientX, clientY, toCanvasRect(rect), transform)
  placedBlocks.value.push({
    id: `${block.id}-${Date.now()}-${placedBlocks.value.length}`,
    blockId: block.id,
    label: block.label,
    tone: block.tone,
    x: Math.round(point.x),
    y: Math.round(point.y)
  })
}

function startPointerBlockDrag(block: BlockDefinition, event: PointerEvent) {
  if (event.button !== 0) {
    return
  }

  event.preventDefault()
  beginBlockDrag(block, event.clientX, event.clientY, event.pointerId)
  ;(event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId)
}

function movePointerBlockDrag(event: PointerEvent) {
  if (!blockDragState || blockDragState.pointerId !== event.pointerId) {
    return
  }

  updateBlockDrag(event.clientX, event.clientY)
}

function endPointerBlockDrag(event: PointerEvent) {
  if (!blockDragState || blockDragState.pointerId !== event.pointerId) {
    return
  }

  finishBlockDrag(event.clientX, event.clientY)
  ;(event.currentTarget as HTMLElement).releasePointerCapture?.(event.pointerId)
}

function moveMouseBlockDrag(event: MouseEvent) {
  if (!blockDragState || blockDragState.pointerId !== null) {
    return
  }

  updateBlockDrag(event.clientX, event.clientY)
}

function endMouseBlockDrag(event: MouseEvent) {
  if (!blockDragState || blockDragState.pointerId !== null) {
    return
  }

  finishBlockDrag(event.clientX, event.clientY)
  window.removeEventListener('mousemove', moveMouseBlockDrag)
  window.removeEventListener('mouseup', endMouseBlockDrag)
}

function startMouseBlockDrag(block: BlockDefinition, event: MouseEvent) {
  if (event.button !== 0 || blockDragState) {
    return
  }

  event.preventDefault()
  beginBlockDrag(block, event.clientX, event.clientY, null)
  window.addEventListener('mousemove', moveMouseBlockDrag)
  window.addEventListener('mouseup', endMouseBlockDrag)
}

onBeforeUnmount(() => {
  window.removeEventListener('mousemove', moveMouseBlockDrag)
  window.removeEventListener('mouseup', endMouseBlockDrag)
})

function allowCanvasDrop(event: DragEvent) {
  event.preventDefault()
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'copy'
  }
}

function dropBlock(event: DragEvent) {
  event.preventDefault()
  const blockId = event.dataTransfer?.getData('application/sts-block')
  const block = blockDefinitions.find((definition) => definition.id === blockId)
  const rect = canvasRef.value?.getBoundingClientRect()

  if (!block || !rect) {
    return
  }

  addBlockAtClientPoint(block, event.clientX, event.clientY)
}

function applyTransform(nextTransform: CanvasTransform) {
  transform.x = nextTransform.x
  transform.y = nextTransform.y
  transform.scale = nextTransform.scale
}

function zoomCanvas(event: WheelEvent) {
  const rect = canvasRef.value?.getBoundingClientRect()
  if (!rect) {
    return
  }

  event.preventDefault()
  applyTransform(
    zoomTransformAtPoint(transform, toCanvasRect(rect), event.clientX, event.clientY, event.deltaY)
  )
}

function zoomBy(direction: 1 | -1) {
  const rect = canvasRef.value?.getBoundingClientRect()
  if (!rect) {
    return
  }

  applyTransform(
    zoomTransformAtPoint(
      transform,
      toCanvasRect(rect),
      rect.left + rect.width / 2,
      rect.top + rect.height / 2,
      direction > 0 ? -180 : 180
    )
  )
}

function resetView() {
  transform.x = 0
  transform.y = 0
  transform.scale = 1
}

function startCanvasPan(event: PointerEvent) {
  if (
    event.button !== 0 ||
    (event.target as HTMLElement).closest('.floating-block-library, .canvas-block, .canvas-controls')
  ) {
    return
  }

  isPanning.value = true
  panState = {
    startPointer: { clientX: event.clientX, clientY: event.clientY },
    startOffset: { x: transform.x, y: transform.y }
  }
  ;(event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId)
}

function moveCanvasPan(event: PointerEvent) {
  if (!panState) {
    return
  }

  const nextOffset = dragOffsetFromPointer(panState.startOffset, panState.startPointer, event)
  transform.x = nextOffset.x
  transform.y = nextOffset.y
}

function endCanvasPan(event: PointerEvent) {
  if (!panState) {
    return
  }

  panState = null
  isPanning.value = false
  ;(event.currentTarget as HTMLElement).releasePointerCapture?.(event.pointerId)
}

function startLibraryDrag(event: PointerEvent) {
  isDraggingLibrary.value = true
  libraryDragState = {
    startPointer: { clientX: event.clientX, clientY: event.clientY },
    startOffset: { x: libraryOffset.x, y: libraryOffset.y }
  }
  ;(event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId)
}

function moveLibraryDrag(event: PointerEvent) {
  if (!libraryDragState) {
    return
  }

  const nextOffset = dragOffsetFromPointer(
    libraryDragState.startOffset,
    libraryDragState.startPointer,
    event
  )
  libraryOffset.x = nextOffset.x
  libraryOffset.y = nextOffset.y
}

function endLibraryDrag(event: PointerEvent) {
  if (!libraryDragState) {
    return
  }

  libraryDragState = null
  isDraggingLibrary.value = false
  ;(event.currentTarget as HTMLElement).releasePointerCapture?.(event.pointerId)
}
</script>

<template>
  <section
    ref="canvasRef"
    class="builder-canvas"
    :class="{ 'is-panning': isPanning }"
    :style="canvasStyle"
    aria-label="策略搭建画布"
    @dragover="allowCanvasDrop"
    @drop="dropBlock"
    @pointerdown="startCanvasPan"
    @pointermove="moveCanvasPan"
    @pointerup="endCanvasPan"
    @pointercancel="endCanvasPan"
    @wheel="zoomCanvas"
  >
    <div class="canvas-world" :style="worldStyle">
      <article
        v-for="block in placedBlocks"
        :key="block.id"
        class="canvas-block"
        :class="`canvas-block--${block.tone}`"
        :style="{ transform: `translate(${block.x}px, ${block.y}px)` }"
      >
        <span>{{ block.label }}</span>
      </article>
    </div>

    <div
      v-if="draggingBlock"
      class="drag-preview"
      :class="`drag-preview--${draggingBlock.block.tone}`"
      :style="{ left: `${draggingBlock.x}px`, top: `${draggingBlock.y}px` }"
    >
      {{ draggingBlock.block.label }}
    </div>

    <aside
      class="block-library floating-block-library"
      :class="{ 'is-dragging': isDraggingLibrary }"
      :style="libraryStyle"
      aria-label="积木库"
    >
      <header
        class="block-library-header"
        @pointerdown.stop="startLibraryDrag"
        @pointermove.stop="moveLibraryDrag"
        @pointerup.stop="endLibraryDrag"
        @pointercancel.stop="endLibraryDrag"
      >
        <h2>积木库</h2>
        <span aria-hidden="true">••</span>
      </header>
      <input placeholder="搜索积木" />
      <nav>
        <button
          v-for="block in blockDefinitions"
          :key="block.id"
          class="library-block"
          :class="`library-block--${block.tone}`"
          :data-block-id="block.id"
          draggable="false"
          @dragstart="startBlockDrag(block, $event)"
          @pointerdown.stop="startPointerBlockDrag(block, $event)"
          @pointermove.stop="movePointerBlockDrag"
          @pointerup.stop="endPointerBlockDrag"
          @pointercancel.stop="endPointerBlockDrag"
          @mousedown.stop="startMouseBlockDrag(block, $event)"
        >
          <span>{{ block.label }}</span>
          <small>{{ block.category }}</small>
        </button>
      </nav>
    </aside>

    <div class="canvas-controls" @pointerdown.stop>
      <button type="button" aria-label="缩小画布" @click="zoomBy(-1)">-</button>
      <span>{{ zoomLabel }}</span>
      <button type="button" aria-label="放大画布" @click="zoomBy(1)">+</button>
      <button type="button" aria-label="重置视图" @click="resetView">↺</button>
    </div>
  </section>
</template>
