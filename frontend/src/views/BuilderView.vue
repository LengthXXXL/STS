<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import {
  dragOffsetFromPointer,
  screenToCanvasPoint,
  snapCanvasPoint,
  zoomTransformAtPoint,
  type CanvasPoint,
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

interface Connection {
  id: string
  fromBlockId: string
  toBlockId: string
}

interface ActiveConnection {
  fromBlockId: string
  x: number
  y: number
}

interface ContextMenuState {
  type: 'block' | 'connection'
  targetId: string
  x: number
  y: number
}

interface DragState {
  startPointer: { clientX: number; clientY: number }
  startOffset: { x: number; y: number }
}

interface PlacedBlockDragState {
  blockId: string
  pointerId: number
  startPointer: CanvasPoint
  startBlock: CanvasPoint
}

const BLOCK_WIDTH = 132
const BLOCK_HEIGHT = 44

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
const connections = ref<Connection[]>([])
const draggingBlock = ref<{ block: BlockDefinition; x: number; y: number } | null>(null)
const activeConnection = ref<ActiveConnection | null>(null)
const selectedBlockId = ref<string | null>(null)
const contextMenu = ref<ContextMenuState | null>(null)
const isPanning = ref(false)
const isDraggingLibrary = ref(false)
const isSnapEnabled = ref(true)

let panState: DragState | null = null
let libraryDragState: DragState | null = null
let blockDragState: { block: BlockDefinition; pointerId: number | null } | null = null
let placedBlockDragState: PlacedBlockDragState | null = null

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

const connectionPaths = computed(() =>
  connections.value
    .map((connection) => {
      const fromBlock = findPlacedBlock(connection.fromBlockId)
      const toBlock = findPlacedBlock(connection.toBlockId)

      if (!fromBlock || !toBlock) {
        return null
      }

      return {
        id: connection.id,
        d: createConnectionPath(outputPortPoint(fromBlock), inputPortPoint(toBlock))
      }
    })
    .filter((path): path is { id: string; d: string } => path !== null)
)

const activeConnectionPath = computed(() => {
  if (!activeConnection.value) {
    return ''
  }

  const fromBlock = findPlacedBlock(activeConnection.value.fromBlockId)
  if (!fromBlock) {
    return ''
  }

  return createConnectionPath(outputPortPoint(fromBlock), activeConnection.value)
})

function toCanvasRect(rect: DOMRect): CanvasRect {
  return {
    left: rect.left,
    top: rect.top,
    width: rect.width,
    height: rect.height
  }
}

function findPlacedBlock(blockId: string) {
  return placedBlocks.value.find((block) => block.id === blockId)
}

function inputPortPoint(block: PlacedBlock) {
  return {
    x: block.x,
    y: block.y + BLOCK_HEIGHT / 2
  }
}

function outputPortPoint(block: PlacedBlock) {
  return {
    x: block.x + BLOCK_WIDTH,
    y: block.y + BLOCK_HEIGHT / 2
  }
}

function createConnectionPath(from: CanvasPoint, to: CanvasPoint) {
  const controlOffset = Math.max(36, Math.abs(to.x - from.x) / 2)
  return [
    `M ${from.x} ${from.y}`,
    `C ${from.x + controlOffset} ${from.y}`,
    `${to.x - controlOffset} ${to.y}`,
    `${to.x} ${to.y}`
  ].join(' ')
}

function snapBlockPosition(position: CanvasPoint, movingId?: string) {
  return snapCanvasPoint(position, {
    enabled: isSnapEnabled.value,
    movingId,
    targets: placedBlocks.value.map((block) => ({
      id: block.id,
      x: block.x,
      y: block.y
    }))
  })
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
  const position = snapBlockPosition(point)
  placedBlocks.value.push({
    id: `${block.id}-${Date.now()}-${placedBlocks.value.length}`,
    blockId: block.id,
    label: block.label,
    tone: block.tone,
    x: Math.round(position.x),
    y: Math.round(position.y)
  })
}

function selectBlock(blockId: string) {
  selectedBlockId.value = blockId
}

function deleteBlock(blockId: string) {
  placedBlocks.value = placedBlocks.value.filter((block) => block.id !== blockId)
  connections.value = connections.value.filter(
    (connection) => connection.fromBlockId !== blockId && connection.toBlockId !== blockId
  )

  if (selectedBlockId.value === blockId) {
    selectedBlockId.value = null
  }
}

function deleteConnection(connectionId: string) {
  connections.value = connections.value.filter((connection) => connection.id !== connectionId)
}

function openBlockContextMenu(blockId: string, event: MouseEvent) {
  event.preventDefault()
  selectBlock(blockId)
  contextMenu.value = {
    type: 'block',
    targetId: blockId,
    x: event.clientX,
    y: event.clientY
  }
}

function openConnectionContextMenu(connectionId: string, event: MouseEvent) {
  event.preventDefault()
  contextMenu.value = {
    type: 'connection',
    targetId: connectionId,
    x: event.clientX,
    y: event.clientY
  }
}

function deleteContextMenuTarget() {
  if (!contextMenu.value) {
    return
  }

  if (contextMenu.value.type === 'block') {
    deleteBlock(contextMenu.value.targetId)
  } else {
    deleteConnection(contextMenu.value.targetId)
  }

  contextMenu.value = null
}

function closeContextMenu() {
  contextMenu.value = null
}

function startPlacedBlockDrag(block: PlacedBlock, event: PointerEvent) {
  if (event.button !== 0) {
    return
  }

  const rect = canvasRef.value?.getBoundingClientRect()
  if (!rect) {
    return
  }

  event.preventDefault()
  selectBlock(block.id)
  placedBlockDragState = {
    blockId: block.id,
    pointerId: event.pointerId,
    startPointer: screenToCanvasPoint(event.clientX, event.clientY, toCanvasRect(rect), transform),
    startBlock: { x: block.x, y: block.y }
  }
  ;(event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId)
}

function movePlacedBlockDrag(event: PointerEvent) {
  if (!placedBlockDragState || placedBlockDragState.pointerId !== event.pointerId) {
    return
  }

  const rect = canvasRef.value?.getBoundingClientRect()
  const block = findPlacedBlock(placedBlockDragState.blockId)
  if (!rect || !block) {
    return
  }

  const currentPointer = screenToCanvasPoint(event.clientX, event.clientY, toCanvasRect(rect), transform)
  const nextPosition = snapBlockPosition(
    {
      x: placedBlockDragState.startBlock.x + currentPointer.x - placedBlockDragState.startPointer.x,
      y: placedBlockDragState.startBlock.y + currentPointer.y - placedBlockDragState.startPointer.y
    },
    block.id
  )
  block.x = Math.round(nextPosition.x)
  block.y = Math.round(nextPosition.y)
}

function endPlacedBlockDrag(event: PointerEvent) {
  if (!placedBlockDragState || placedBlockDragState.pointerId !== event.pointerId) {
    return
  }

  placedBlockDragState = null
  ;(event.currentTarget as HTMLElement).releasePointerCapture?.(event.pointerId)
}

function startConnection(blockId: string, event: PointerEvent) {
  const rect = canvasRef.value?.getBoundingClientRect()
  if (!rect) {
    return
  }

  event.preventDefault()
  selectBlock(blockId)
  activeConnection.value = {
    fromBlockId: blockId,
    ...screenToCanvasPoint(event.clientX, event.clientY, toCanvasRect(rect), transform)
  }
}

function updateActiveConnection(event: PointerEvent) {
  const rect = canvasRef.value?.getBoundingClientRect()
  if (!activeConnection.value || !rect) {
    return
  }

  const point = screenToCanvasPoint(event.clientX, event.clientY, toCanvasRect(rect), transform)
  activeConnection.value.x = point.x
  activeConnection.value.y = point.y
}

function finishConnection(toBlockId: string, event: PointerEvent) {
  event.preventDefault()
  if (!activeConnection.value || activeConnection.value.fromBlockId === toBlockId) {
    activeConnection.value = null
    return
  }

  const exists = connections.value.some(
    (connection) =>
      connection.fromBlockId === activeConnection.value?.fromBlockId &&
      connection.toBlockId === toBlockId
  )
  if (!exists) {
    connections.value.push({
      id: `${activeConnection.value.fromBlockId}-${toBlockId}`,
      fromBlockId: activeConnection.value.fromBlockId,
      toBlockId
    })
  }

  activeConnection.value = null
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
  removeMouseBlockDragListeners()
}

function cancelMouseBlockDrag() {
  if (!blockDragState || blockDragState.pointerId !== null) {
    return
  }

  draggingBlock.value = null
  blockDragState = null
  removeMouseBlockDragListeners()
}

function removeMouseBlockDragListeners() {
  window.removeEventListener('mousemove', moveMouseBlockDrag)
  window.removeEventListener('mouseup', endMouseBlockDrag)
  window.removeEventListener('blur', cancelMouseBlockDrag)
}

function startMouseBlockDrag(block: BlockDefinition, event: MouseEvent) {
  if (event.button !== 0 || blockDragState) {
    return
  }

  event.preventDefault()
  beginBlockDrag(block, event.clientX, event.clientY, null)
  window.addEventListener('mousemove', moveMouseBlockDrag)
  window.addEventListener('mouseup', endMouseBlockDrag)
  window.addEventListener('blur', cancelMouseBlockDrag)
}

onBeforeUnmount(() => {
  removeMouseBlockDragListeners()
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
  closeContextMenu()

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
  if (activeConnection.value) {
    updateActiveConnection(event)
    return
  }

  if (!panState) {
    return
  }

  const nextOffset = dragOffsetFromPointer(panState.startOffset, panState.startPointer, event)
  transform.x = nextOffset.x
  transform.y = nextOffset.y
}

function endCanvasPan(event: PointerEvent) {
  if (activeConnection.value) {
    activeConnection.value = null
    return
  }

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

function toggleSnap() {
  isSnapEnabled.value = !isSnapEnabled.value
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
    @click="closeContextMenu"
    @contextmenu.prevent="closeContextMenu"
  >
    <div class="canvas-world" :style="worldStyle">
      <svg class="connection-layer" aria-hidden="true">
        <path
          v-for="path in connectionPaths"
          :key="path.id"
          class="connection-path"
          :d="path.d"
          :data-connection-id="path.id"
          @contextmenu.prevent.stop="openConnectionContextMenu(path.id, $event)"
        />
        <path
          v-if="activeConnectionPath"
          class="connection-path connection-path--draft"
          :d="activeConnectionPath"
        />
      </svg>

      <article
        v-for="block in placedBlocks"
        :key="block.id"
        class="canvas-block"
        :class="[`canvas-block--${block.tone}`, { 'is-selected': selectedBlockId === block.id }]"
        :style="{ transform: `translate(${block.x}px, ${block.y}px)` }"
        @click.stop="selectBlock(block.id)"
        @pointerdown.stop="startPlacedBlockDrag(block, $event)"
        @pointermove.stop="movePlacedBlockDrag"
        @pointerup.stop="endPlacedBlockDrag"
        @pointercancel.stop="endPlacedBlockDrag"
        @contextmenu.prevent.stop="openBlockContextMenu(block.id, $event)"
      >
        <span
          class="connection-port connection-port--input"
          data-port="input"
          aria-label="输入端口"
          @pointerup.stop="finishConnection(block.id, $event)"
        />
        <span>{{ block.label }}</span>
        <span
          class="connection-port connection-port--output"
          data-port="output"
          aria-label="输出端口"
          @pointerdown.stop="startConnection(block.id, $event)"
        />
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
      <button
        class="snap-toggle"
        type="button"
        :aria-pressed="isSnapEnabled"
        @click="toggleSnap"
      >
        磁吸{{ isSnapEnabled ? '开' : '关' }}
      </button>
    </div>

    <div
      v-if="contextMenu"
      class="context-menu"
      :style="{ left: `${contextMenu.x}px`, top: `${contextMenu.y}px` }"
      @click.stop
      @pointerdown.stop
      @contextmenu.prevent.stop
    >
      <button class="context-menu-delete" type="button" @click="deleteContextMenuTarget">
        删除{{ contextMenu.type === 'block' ? '积木' : '连接' }}
      </button>
    </div>
  </section>
</template>
