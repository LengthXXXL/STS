<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  dragOffsetFromPointer,
  screenToCanvasPoint,
  snapCanvasPoint,
  zoomTransformAtPoint,
  type CanvasPoint,
  type CanvasRect,
  type CanvasTransform
} from '../utils/builderCanvas'
import { apiClient } from '../api/http'
import { useAuthStore } from '../stores/auth'
import { useStrategyWorkspaceStore } from '../stores/strategyWorkspace'

interface BlockDefinition {
  id: string
  label: string
  category: string
  tone: 'action' | 'risk' | 'condition' | 'indicator' | 'position' | 'time'
  fields: BlockParamField[]
}

interface BlockParamField {
  key: string
  label: string
  type: 'text' | 'number' | 'select'
  defaultValue: string
  suffix?: string
  min?: string
  max?: string
  step?: string
  options?: Array<{ label: string; value: string }>
}

interface PlacedBlock {
  id: string
  blockId: string
  label: string
  tone: BlockDefinition['tone']
  x: number
  y: number
  params: Record<string, string>
}

interface StrategyDraft {
  version: 1
  nodes: StrategyNode[]
  edges: StrategyEdge[]
  viewport: CanvasTransform
}

interface StrategyNode {
  id: string
  type: string
  label: string
  x: number
  y: number
  params: Record<string, string>
}

interface StrategyEdge {
  id: string
  from: string
  to: string
}

interface ValidationIssue {
  id: string
  message: string
}

interface BacktestSettings {
  market: 'A_SHARE' | 'US_STOCK'
  symbol: string
  timeframe: '5m' | '1m'
  startDate: string
  endDate: string
  initialCash: string
}

interface BacktestConfig {
  market: BacktestSettings['market']
  symbol: string
  timeframe: BacktestSettings['timeframe']
  startDate: string
  endDate: string
  initialCash: number
  simulationAccountId?: number
}

interface SimulationAccount {
  id: number
  name: string
  market: BacktestSettings['market']
  initialCash: number
}

interface SimulationAccountListResponse {
  items: SimulationAccount[]
  total: number
  page: number
  pageSize: number
}

interface BacktestSummaryResult {
  totalReturnPercent: number
  maxDrawdownPercent: number
  winRatePercent: number
  endingEquity: number
  tradeCount: number
}

interface BacktestTradeResult {
  time: string
  side: 'BUY' | 'SELL'
  price: number
  quantity: number
  reason: string
}

interface EquityPointResult {
  time: string
  equity: number
}

interface BacktestRunResult {
  runId: string
  status: 'COMPLETED'
  config: BacktestConfig
  summary: BacktestSummaryResult
  trades: BacktestTradeResult[]
  equityCurve: EquityPointResult[]
}

interface SavedStrategyResponse {
  id: number
  name: string
  strategy: StrategyDraft
  backtestConfig: BacktestConfig | null
}

interface CustomBlockResponse {
  id: number
  name: string
}

interface CustomBlockTemplate {
  id: number
  ownerId: number
  name: string
  description: string | null
  category: string
  tags: string[]
  template: StrategyDraft
  reviewStatus: 'private' | 'pending_review' | 'approved' | 'rejected'
  createdAt: string
  updatedAt: string
}

interface CustomBlockListResponse {
  items: CustomBlockTemplate[]
  total: number
  page: number
  pageSize: number
}

type ReviewMode = 'backtest' | 'publish'

interface CustomBlockForm {
  name: string
  category: string
  description: string
  tags: string
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
  type: 'connection'
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
  hasMoved: boolean
}

type LibraryDragSource =
  | { type: 'builtin'; block: BlockDefinition }
  | { type: 'custom'; block: CustomBlockTemplate }

const BLOCK_WIDTH = 132
const BLOCK_HEIGHT = 44
const STRATEGY_DRAFT_STORAGE_KEY = 'sts.builder.strategyDraft.v1'
const blockCategoryOrder = ['动作', '条件', '行情指标', '持仓', '时间', '风控']
const DEFAULT_STRATEGY_NAME = '未命名策略'

const blockDefinitions: BlockDefinition[] = [
  {
    id: 'buy',
    label: '买入',
    category: '动作',
    tone: 'action',
    fields: [
      {
        key: 'sizePercent',
        label: '买入仓位',
        type: 'number',
        defaultValue: '20',
        min: '1',
        max: '100',
        step: '1',
        suffix: '%'
      },
      {
        key: 'orderType',
        label: '委托方式',
        type: 'select',
        defaultValue: 'market',
        options: [
          { label: '市价', value: 'market' },
          { label: '限价', value: 'limit' }
        ]
      }
    ]
  },
  {
    id: 'sell',
    label: '卖出',
    category: '动作',
    tone: 'action',
    fields: [
      {
        key: 'sellPercent',
        label: '卖出仓位',
        type: 'number',
        defaultValue: '50',
        min: '1',
        max: '100',
        step: '1',
        suffix: '%'
      },
      {
        key: 'orderType',
        label: '委托方式',
        type: 'select',
        defaultValue: 'market',
        options: [
          { label: '市价', value: 'market' },
          { label: '限价', value: 'limit' }
        ]
      }
    ]
  },
  {
    id: 'clear',
    label: '清仓',
    category: '动作',
    tone: 'action',
    fields: [
      {
        key: 'sellPercent',
        label: '清仓比例',
        type: 'number',
        defaultValue: '100',
        min: '1',
        max: '100',
        step: '1',
        suffix: '%'
      },
      { key: 'reason', label: '触发说明', type: 'text', defaultValue: '退出全部持仓' }
    ]
  },
  {
    id: 'if',
    label: '如果',
    category: '条件',
    tone: 'condition',
    fields: [
      {
        key: 'mode',
        label: '条件组合',
        type: 'select',
        defaultValue: 'all',
        options: [
          { label: '全部满足', value: 'all' },
          { label: '任一满足', value: 'any' }
        ]
      }
    ]
  },
  {
    id: 'current-price',
    label: '当前价',
    category: '行情指标',
    tone: 'indicator',
    fields: [
      {
        key: 'comparator',
        label: '比较方式',
        type: 'select',
        defaultValue: '>=',
        options: [
          { label: '大于等于', value: '>=' },
          { label: '小于等于', value: '<=' }
        ]
      },
      {
        key: 'price',
        label: '价格',
        type: 'number',
        defaultValue: '10',
        min: '0',
        step: '0.01'
      }
    ]
  },
  {
    id: 'price-change',
    label: 'N根收益率',
    category: '行情指标',
    tone: 'indicator',
    fields: [
      {
        key: 'lookbackBars',
        label: '回看K线数',
        type: 'number',
        defaultValue: '1',
        min: '1',
        step: '1'
      },
      {
        key: 'comparator',
        label: '比较方式',
        type: 'select',
        defaultValue: '>=',
        options: [
          { label: '大于等于', value: '>=' },
          { label: '小于等于', value: '<=' }
        ]
      },
      {
        key: 'changePercent',
        label: '收益率',
        type: 'number',
        defaultValue: '5',
        step: '0.1',
        suffix: '%'
      }
    ]
  },
  {
    id: 'moving-average',
    label: '均线',
    category: '行情指标',
    tone: 'indicator',
    fields: [
      {
        key: 'period',
        label: '均线周期',
        type: 'number',
        defaultValue: '5',
        min: '1',
        step: '1'
      },
      {
        key: 'relation',
        label: '价格位置',
        type: 'select',
        defaultValue: 'above',
        options: [
          { label: '价格在均线上方', value: 'above' },
          { label: '价格在均线下方', value: 'below' }
        ]
      }
    ]
  },
  {
    id: 'volume-change',
    label: '成交量变化',
    category: '行情指标',
    tone: 'indicator',
    fields: [
      {
        key: 'lookbackBars',
        label: '回看K线数',
        type: 'number',
        defaultValue: '1',
        min: '1',
        step: '1'
      },
      {
        key: 'comparator',
        label: '比较方式',
        type: 'select',
        defaultValue: '>=',
        options: [
          { label: '大于等于', value: '>=' },
          { label: '小于等于', value: '<=' }
        ]
      },
      {
        key: 'changePercent',
        label: '成交量变化',
        type: 'number',
        defaultValue: '20',
        step: '1',
        suffix: '%'
      }
    ]
  },
  {
    id: 'position-state',
    label: '持仓状态',
    category: '持仓',
    tone: 'position',
    fields: [
      {
        key: 'state',
        label: '判断内容',
        type: 'select',
        defaultValue: 'no-position',
        options: [
          { label: '没有持仓', value: 'no-position' },
          { label: '已有持仓', value: 'has-position' },
          { label: '持仓收益率 >=', value: 'profit-gte' },
          { label: '持仓K线数 >=', value: 'holding-bars-gte' }
        ]
      },
      {
        key: 'threshold',
        label: '阈值',
        type: 'number',
        defaultValue: '3',
        step: '0.1'
      }
    ]
  },
  {
    id: 'time-window',
    label: '交易时段',
    category: '时间',
    tone: 'time',
    fields: [
      { key: 'startTime', label: '开始时间', type: 'text', defaultValue: '09:35' },
      { key: 'endTime', label: '结束时间', type: 'text', defaultValue: '14:55' }
    ]
  },
  {
    id: 'take-profit',
    label: '止盈',
    category: '风控',
    tone: 'risk',
    fields: [
      {
        key: 'profitRate',
        label: '持仓收益率 >=',
        type: 'number',
        defaultValue: '5',
        min: '0',
        step: '0.1',
        suffix: '%'
      },
      {
        key: 'sellPercent',
        label: '卖出仓位',
        type: 'number',
        defaultValue: '50',
        min: '1',
        max: '100',
        step: '1',
        suffix: '%'
      }
    ]
  },
  {
    id: 'stop-loss',
    label: '止损',
    category: '风控',
    tone: 'risk',
    fields: [
      {
        key: 'lossRate',
        label: '持仓亏损率 >=',
        type: 'number',
        defaultValue: '3',
        min: '0',
        step: '0.1',
        suffix: '%'
      },
      {
        key: 'sellPercent',
        label: '卖出仓位',
        type: 'number',
        defaultValue: '100',
        min: '1',
        max: '100',
        step: '1',
        suffix: '%'
      }
    ]
  },
  {
    id: 'moving-stop',
    label: '移动止损',
    category: '风控',
    tone: 'risk',
    fields: [
      {
        key: 'minProfitPercent',
        label: '最高收益至少',
        type: 'number',
        defaultValue: '5',
        min: '0',
        step: '0.1',
        suffix: '%'
      },
      {
        key: 'trailPercent',
        label: '从高点回落',
        type: 'number',
        defaultValue: '3',
        min: '0',
        step: '0.1',
        suffix: '%'
      },
      {
        key: 'sellPercent',
        label: '卖出仓位',
        type: 'number',
        defaultValue: '100',
        min: '1',
        max: '100',
        step: '1',
        suffix: '%'
      }
    ]
  },
  {
    id: 'cooldown',
    label: '冷却',
    category: '风控',
    tone: 'condition',
    fields: [
      { key: 'abnormalRule', label: '异常条件', type: 'text', defaultValue: '连续亏损2次' },
      { key: 'durationBars', label: '冷却K线数', type: 'number', defaultValue: '3', min: '1', step: '1' }
    ]
  }
]

const canvasRef = ref<HTMLElement | null>(null)
const libraryRef = ref<HTMLElement | null>(null)
const router = useRouter()
const authStore = useAuthStore()
const strategyWorkspaceStore = useStrategyWorkspaceStore()
const transform = reactive<CanvasTransform>({ x: 0, y: 0, scale: 1 })
const libraryOffset = reactive({ x: 0, y: 0 })
const placedBlocks = ref<PlacedBlock[]>([])
const connections = ref<Connection[]>([])
const draggingBlock = ref<{
  label: string
  tone: BlockDefinition['tone']
  x: number
  y: number
} | null>(null)
const activeConnection = ref<ActiveConnection | null>(null)
const selectedBlockId = ref<string | null>(null)
const inspectedBlockId = ref<string | null>(null)
const contextMenu = ref<ContextMenuState | null>(null)
const blockSearchQuery = ref('')
const draftStatus = ref('尚未保存')
const isPanning = ref(false)
const isDraggingLibrary = ref(false)
const isLibraryCollapsed = ref(false)
const isSnapEnabled = ref(true)
const reviewModalMode = ref<ReviewMode | null>(null)
const isCustomBlockModalOpen = ref(false)
const isBacktestRunning = ref(false)
const isCustomBlockSaving = ref(false)
const backtestRunError = ref('')
const backtestRunResult = ref<BacktestRunResult | null>(null)
const backtestPersistStatus = ref('')
const simulationAccounts = ref<SimulationAccount[]>([])
const selectedSimulationAccountId = ref('')
const isLoadingSimulationAccounts = ref(false)
const simulationAccountError = ref('')
const currentStrategyId = ref<number | null>(null)
const currentStrategyName = ref(DEFAULT_STRATEGY_NAME)
const isSavingStrategy = ref(false)
const strategySaveStatus = ref('')
const customBlockForm = reactive<CustomBlockForm>({
  name: '',
  category: '自定义',
  description: '',
  tags: ''
})
const customBlockStatus = ref('')
const customBlockLibrary = ref<CustomBlockTemplate[]>([])
const customBlockLibraryLoading = ref(false)
const customBlockLibraryError = ref('')
const backtestSettings = reactive<BacktestSettings>({
  market: 'A_SHARE',
  symbol: '000001.SZ',
  timeframe: '5m',
  startDate: '2026-01-01',
  endDate: '2026-03-01',
  initialCash: '100000'
})

let panState: DragState | null = null
let libraryDragState: DragState | null = null
let blockDragState: { source: LibraryDragSource; pointerId: number | null } | null = null
let blockDragPointerTarget: HTMLElement | null = null
let placedBlockDragState: PlacedBlockDragState | null = null
let ignoredPlacedBlockClickId: string | null = null

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

const selectedBlock = computed(() => {
  if (!inspectedBlockId.value) {
    return null
  }

  return findPlacedBlock(inspectedBlockId.value) ?? null
})

const selectedBlockDefinition = computed(() => {
  if (!selectedBlock.value) {
    return null
  }

  return (
    blockDefinitions.find((definition) => definition.id === selectedBlock.value?.blockId) ?? null
  )
})

const selectedBlockFields = computed(() => selectedBlockDefinition.value?.fields ?? [])

const filteredBlockDefinitions = computed(() => {
  const keyword = blockSearchQuery.value.trim().toLowerCase()
  if (!keyword) {
    return blockDefinitions
  }

  return blockDefinitions.filter((block) => {
    return [block.label, block.category, block.id].some((text) =>
      text.toLowerCase().includes(keyword)
    )
  })
})

const filteredBlockGroups = computed(() =>
  blockCategoryOrder
    .map((category) => ({
      category,
      blocks: filteredBlockDefinitions.value.filter((block) => block.category === category)
    }))
    .filter((group) => group.blocks.length > 0)
)

const filteredCustomBlocks = computed(() => {
  const keyword = blockSearchQuery.value.trim().toLowerCase()
  if (!keyword) {
    return customBlockLibrary.value
  }

  return customBlockLibrary.value.filter((block) => {
    const nodeLabels = block.template.nodes.map((node) => node.label || node.type)
    return [
      block.name,
      block.description ?? '',
      block.category,
      ...block.tags,
      ...nodeLabels
    ].some((text) => text.toLowerCase().includes(keyword))
  })
})

const strategyDraft = computed<StrategyDraft>(() => ({
  version: 1,
  nodes: placedBlocks.value.map((block) => ({
    id: block.id,
    type: block.blockId,
    label: block.label,
    x: block.x,
    y: block.y,
    params: { ...block.params }
  })),
  edges: connections.value.map((connection) => ({
    id: connection.id,
    from: connection.fromBlockId,
    to: connection.toBlockId
  })),
  viewport: {
    x: transform.x,
    y: transform.y,
    scale: transform.scale
  }
}))

const strategyJson = computed(() => JSON.stringify(strategyDraft.value, null, 2))

const validationIssues = computed<ValidationIssue[]>(() => {
  if (strategyDraft.value.nodes.length === 0) {
    return [{ id: 'empty-nodes', message: '请至少放置一个积木' }]
  }

  const issues: ValidationIssue[] = []
  const hasTradeAction = strategyDraft.value.nodes.some((node) =>
    ['buy', 'sell', 'clear'].includes(node.type)
  )

  if (!hasTradeAction) {
    issues.push({ id: 'missing-trade-action', message: '策略至少需要一个买入、卖出或清仓动作' })
  }

  strategyDraft.value.nodes.forEach((node) => {
    const definition = blockDefinitions.find((block) => block.id === node.type)
    definition?.fields.forEach((field) => {
      const value = node.params[field.key]
      if (value === undefined || value.trim() === '') {
        issues.push({
          id: `${node.id}-${field.key}-empty`,
          message: `${node.label} 的 ${field.label} 不能为空`
        })
      }
    })
  })

  return issues
})

const validationSummary = computed(() =>
  validationIssues.value.length > 0 ? '需完善' : '可运行'
)

const backtestConfig = computed<BacktestConfig>(() => ({
  market: backtestSettings.market,
  symbol: backtestSettings.symbol.trim(),
  timeframe: backtestSettings.timeframe,
  startDate: backtestSettings.startDate,
  endDate: backtestSettings.endDate,
  initialCash: Number(backtestSettings.initialCash) || 0,
  ...(selectedSimulationAccountId.value
    ? { simulationAccountId: Number(selectedSimulationAccountId.value) }
    : {})
}))

const backtestIssues = computed<ValidationIssue[]>(() => {
  const issues: ValidationIssue[] = []

  if (validationIssues.value.length > 0) {
    issues.push({ id: 'strategy-not-ready', message: '策略校验通过后才能运行回测' })
  }

  if (backtestConfig.value.symbol === '') {
    issues.push({ id: 'empty-symbol', message: '股票代码不能为空' })
  }

  if (!backtestConfig.value.startDate || !backtestConfig.value.endDate) {
    issues.push({ id: 'empty-date-range', message: '回测时间范围不能为空' })
  } else {
    const rangeDays = dateRangeDays(backtestConfig.value.startDate, backtestConfig.value.endDate)

    if (rangeDays !== null && rangeDays <= 0) {
      issues.push({ id: 'invalid-date-range', message: '开始日期不能晚于结束日期' })
    }

    if (backtestConfig.value.timeframe === '1m' && rangeDays !== null && rangeDays > 7) {
      issues.push({ id: 'one-minute-range-too-long', message: '1分钟K线最多选择7天范围' })
    }
  }

  if (backtestConfig.value.initialCash <= 0) {
    issues.push({ id: 'invalid-initial-cash', message: '初始资金必须大于0' })
  }

  return issues
})

const backtestSummary = computed(() =>
  backtestIssues.value.length > 0 ? '需完善' : '回测就绪'
)

const backtestJson = computed(() => JSON.stringify(backtestConfig.value, null, 2))

const reviewModalTitle = computed(() =>
  reviewModalMode.value === 'publish' ? '发布前检查' : '运行回测前检查'
)

const reviewPrimaryLabel = computed(() =>
  reviewModalMode.value === 'publish' ? '确认发布' : '开始回测'
)

const reviewPrimaryDisabled = computed(() => {
  if (reviewModalMode.value === 'publish') {
    return validationIssues.value.length > 0
  }

  return backtestIssues.value.length > 0
})

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

function dateRangeDays(startDate: string, endDate: string) {
  const startTime = Date.parse(`${startDate}T00:00:00`)
  const endTime = Date.parse(`${endDate}T00:00:00`)

  if (Number.isNaN(startTime) || Number.isNaN(endTime)) {
    return null
  }

  return Math.round((endTime - startTime) / 86_400_000) + 1
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

function createDefaultParams(block: BlockDefinition) {
  return block.fields.reduce<Record<string, string>>((params, field) => {
    params[field.key] = field.defaultValue
    return params
  }, {})
}

function normalizeBlockParams(block: BlockDefinition, params: unknown) {
  const nextParams = createDefaultParams(block)
  if (!params || typeof params !== 'object') {
    return nextParams
  }

  const savedParams = params as Record<string, unknown>
  block.fields.forEach((field) => {
    const value = savedParams[field.key]
    if (typeof value === 'string') {
      nextParams[field.key] = value
    } else if (typeof value === 'number') {
      nextParams[field.key] = String(value)
    }
  })

  return nextParams
}

function blockParamValue(block: PlacedBlock, field: BlockParamField) {
  return block.params[field.key] ?? field.defaultValue
}

function updateBlockParam(blockId: string, key: string, event: Event) {
  const block = findPlacedBlock(blockId)
  if (
    !block ||
    !(event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement)
  ) {
    return
  }

  block.params = {
    ...block.params,
    [key]: event.target.value
  }
}

function isDraftRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object')
}

function restoreStrategyDraft(draft: unknown, successStatus = '已从本机浏览器加载草稿') {
  if (!isDraftRecord(draft) || !Array.isArray(draft.nodes) || !Array.isArray(draft.edges)) {
    draftStatus.value = '草稿格式无效'
    return
  }

  const nextBlocks = draft.nodes.reduce<PlacedBlock[]>((blocks, node) => {
    if (!isDraftRecord(node) || typeof node.id !== 'string' || typeof node.type !== 'string') {
      return blocks
    }

    const definition = blockDefinitions.find((block) => block.id === node.type)
    if (!definition) {
      return blocks
    }

    blocks.push({
      id: node.id,
      blockId: definition.id,
      label: definition.label,
      tone: definition.tone,
      x: typeof node.x === 'number' ? Math.round(node.x) : 0,
      y: typeof node.y === 'number' ? Math.round(node.y) : 0,
      params: normalizeBlockParams(definition, node.params)
    })
    return blocks
  }, [])

  const blockIds = new Set(nextBlocks.map((block) => block.id))
  const nextConnections = draft.edges.reduce<Connection[]>((edges, edge) => {
    if (
      !isDraftRecord(edge) ||
      typeof edge.id !== 'string' ||
      typeof edge.from !== 'string' ||
      typeof edge.to !== 'string' ||
      !blockIds.has(edge.from) ||
      !blockIds.has(edge.to)
    ) {
      return edges
    }

    edges.push({
      id: edge.id,
      fromBlockId: edge.from,
      toBlockId: edge.to
    })
    return edges
  }, [])

  placedBlocks.value = nextBlocks
  connections.value = nextConnections
  selectedBlockId.value = null
  inspectedBlockId.value = null
  contextMenu.value = null
  activeConnection.value = null
  placedBlockDragState = null
  currentStrategyId.value = null
  currentStrategyName.value = DEFAULT_STRATEGY_NAME

  if (isDraftRecord(draft.viewport)) {
    transform.x = typeof draft.viewport.x === 'number' ? draft.viewport.x : 0
    transform.y = typeof draft.viewport.y === 'number' ? draft.viewport.y : 0
    transform.scale = typeof draft.viewport.scale === 'number' ? draft.viewport.scale : 1
  }

  draftStatus.value = successStatus
}

function applyBacktestConfig(config: BacktestConfig | null) {
  if (!config) {
    return
  }

  selectedSimulationAccountId.value = config.simulationAccountId
    ? String(config.simulationAccountId)
    : ''
  backtestSettings.market = config.market
  backtestSettings.symbol = config.symbol
  backtestSettings.timeframe = config.timeframe
  backtestSettings.startDate = config.startDate
  backtestSettings.endDate = config.endDate
  backtestSettings.initialCash = String(config.initialCash)
}

async function loadSimulationAccounts() {
  if (!authStore.isAuthenticated || isLoadingSimulationAccounts.value) {
    return
  }

  isLoadingSimulationAccounts.value = true
  simulationAccountError.value = ''
  try {
    const response = await apiClient.get<SimulationAccountListResponse>('/simulation-accounts', {
      params: { page: 1, pageSize: 50 }
    })
    simulationAccounts.value = response.data.items

    if (
      selectedSimulationAccountId.value &&
      !simulationAccounts.value.some((account) => String(account.id) === selectedSimulationAccountId.value)
    ) {
      selectedSimulationAccountId.value = ''
    }

    applySelectedSimulationAccount()
  } catch {
    simulationAccountError.value = '模拟账户加载失败'
  } finally {
    isLoadingSimulationAccounts.value = false
  }
}

async function loadCustomBlockLibrary() {
  if (!authStore.isAuthenticated) {
    customBlockLibrary.value = []
    customBlockLibraryError.value = ''
    return
  }

  customBlockLibraryLoading.value = true
  customBlockLibraryError.value = ''
  try {
    const response = await apiClient.get<CustomBlockListResponse>('/custom-blocks', {
      params: { page: 1, pageSize: 50 }
    })
    customBlockLibrary.value = response.data.items
  } catch {
    customBlockLibrary.value = []
    customBlockLibraryError.value = '我的积木加载失败'
  } finally {
    customBlockLibraryLoading.value = false
  }
}

function applySelectedSimulationAccount() {
  const account = simulationAccounts.value.find(
    (item) => String(item.id) === selectedSimulationAccountId.value
  )
  if (!account) {
    return
  }

  backtestSettings.market = account.market
  backtestSettings.initialCash = String(account.initialCash)
}

function loadWorkspaceStrategy() {
  const workspaceDraft = strategyWorkspaceStore.consumePendingWorkspaceDraft()
  if (!workspaceDraft) {
    return
  }

  restoreStrategyDraft(workspaceDraft.strategy, workspaceDraft.statusMessage)
  applyBacktestConfig(workspaceDraft.backtestConfig)
  currentStrategyId.value =
    workspaceDraft.source === 'saved-strategy' ? workspaceDraft.savedStrategyId ?? null : null
  currentStrategyName.value = workspaceDraft.name
  strategySaveStatus.value = workspaceDraft.statusMessage
}

function saveDraft() {
  localStorage.setItem(STRATEGY_DRAFT_STORAGE_KEY, strategyJson.value)
  draftStatus.value = '草稿已保存到本机浏览器'
}

function loadDraft() {
  const rawDraft = localStorage.getItem(STRATEGY_DRAFT_STORAGE_KEY)
  if (!rawDraft) {
    draftStatus.value = '暂无本机浏览器草稿'
    return
  }

  try {
    restoreStrategyDraft(JSON.parse(rawDraft))
  } catch {
    draftStatus.value = '草稿读取失败'
  }
}

async function saveStrategyToSpace() {
  contextMenu.value = null

  if (!authStore.isAuthenticated) {
    strategySaveStatus.value = '请先登录后再保存策略到个人空间'
    window.dispatchEvent(new CustomEvent('sts:auth-required'))
    return
  }

  if (validationIssues.value.length > 0) {
    strategySaveStatus.value = validationIssues.value[0].message
    return
  }

  if (isSavingStrategy.value) {
    return
  }

  isSavingStrategy.value = true
  strategySaveStatus.value = '正在保存策略'

  const payload = {
    name: currentStrategyName.value || DEFAULT_STRATEGY_NAME,
    description: null,
    strategy: strategyDraft.value,
    backtestConfig: backtestConfig.value
  }

  try {
    const response =
      currentStrategyId.value === null
        ? await apiClient.post<SavedStrategyResponse>('/strategies', payload)
        : await apiClient.put<SavedStrategyResponse>(
            `/strategies/${currentStrategyId.value}`,
            payload
          )

    currentStrategyId.value = response.data.id
    currentStrategyName.value = response.data.name
    strategySaveStatus.value =
      currentStrategyId.value === null
        ? '策略已保存到个人空间'
        : `策略已保存到个人空间：${response.data.name}`
  } catch {
    strategySaveStatus.value = '保存失败，请稍后重试'
  } finally {
    isSavingStrategy.value = false
  }
}

function openReviewModal(mode: ReviewMode) {
  reviewModalMode.value = mode
  contextMenu.value = null
  if (mode === 'backtest') {
    void loadSimulationAccounts()
  }
}

function closeReviewModal() {
  reviewModalMode.value = null
}

async function runBacktest() {
  if (backtestIssues.value.length > 0 || isBacktestRunning.value) {
    return
  }

  isBacktestRunning.value = true
  backtestRunError.value = ''
  backtestRunResult.value = null
  backtestPersistStatus.value = ''

  try {
    const response = await apiClient.post<BacktestRunResult>('/backtests/run', {
      strategy: strategyDraft.value,
      config: backtestConfig.value
    })
    backtestRunResult.value = response.data
    backtestPersistStatus.value = authStore.isAuthenticated
      ? '回测结果已保存到个人空间，可在我的回测中查看'
      : '访客回测仅在当前页面展示，登录后运行可保存到个人空间'
  } catch {
    backtestRunError.value = '回测运行失败，请稍后重试'
  } finally {
    isBacktestRunning.value = false
  }
}

function openPersonalBacktests() {
  void router.push({
    path: '/space',
    query: { tab: 'backtests' }
  })
}

function openCustomBlockModal() {
  contextMenu.value = null
  selectedBlockId.value = null
  inspectedBlockId.value = null
  customBlockForm.name =
    currentStrategyName.value === DEFAULT_STRATEGY_NAME
      ? '未命名积木模板'
      : `${currentStrategyName.value}模板`
  customBlockForm.category = '自定义'
  customBlockForm.description = ''
  customBlockForm.tags = ''
  customBlockStatus.value =
    validationIssues.value.length > 0
      ? validationIssues.value[0].message
      : '将当前画布保存为可复用的私有积木模板'
  isCustomBlockModalOpen.value = true
}

function closeCustomBlockModal() {
  if (isCustomBlockSaving.value) {
    return
  }
  isCustomBlockModalOpen.value = false
}

function customBlockTags() {
  return customBlockForm.tags
    .split(/[，,]/)
    .map((tag) => tag.trim())
    .filter((tag, index, tags) => tag && tags.indexOf(tag) === index)
    .slice(0, 12)
}

async function saveCustomBlockTemplate() {
  if (!authStore.isAuthenticated) {
    customBlockStatus.value = '请先登录后再保存自定义积木'
    window.dispatchEvent(new CustomEvent('sts:auth-required'))
    return
  }

  if (validationIssues.value.length > 0) {
    customBlockStatus.value = validationIssues.value[0].message
    return
  }

  const name = customBlockForm.name.trim()
  const category = customBlockForm.category.trim()

  if (!name) {
    customBlockStatus.value = '请填写积木名称'
    return
  }

  if (!category) {
    customBlockStatus.value = '请填写积木分类'
    return
  }

  if (isCustomBlockSaving.value) {
    return
  }

  isCustomBlockSaving.value = true
  customBlockStatus.value = '正在保存到我的积木'

  try {
    const response = await apiClient.post<CustomBlockResponse>('/custom-blocks', {
      name,
      description: customBlockForm.description.trim() || null,
      category,
      tags: customBlockTags(),
      template: strategyDraft.value
    })
    customBlockStatus.value = `已保存到我的积木：${response.data.name}`
    void loadCustomBlockLibrary()
  } catch {
    customBlockStatus.value = '保存自定义积木失败，请稍后重试'
  } finally {
    isCustomBlockSaving.value = false
  }
}

async function handleReviewPrimaryAction() {
  if (reviewModalMode.value === 'backtest') {
    await runBacktest()
    return
  }

  if (validationIssues.value.length > 0) {
    draftStatus.value = validationIssues.value[0].message
    return
  }

  draftStatus.value = '发布接口待接入，当前仅完成发布前检查'
}

function handleBuilderAction(event: Event) {
  const detail = (event as CustomEvent<{ action?: string }>).detail

  if (detail?.action === 'save') {
    void saveStrategyToSpace()
    return
  }

  if (detail?.action === 'backtest' || detail?.action === 'publish') {
    openReviewModal(detail.action)
  }
}

function startBlockDrag(block: BlockDefinition, event: DragEvent) {
  event.dataTransfer?.setData('application/sts-block', block.id)
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'copy'
  }
}

function libraryDragLabel(source: LibraryDragSource) {
  return source.type === 'builtin' ? source.block.label : source.block.name
}

function libraryDragTone(source: LibraryDragSource): BlockDefinition['tone'] {
  return source.type === 'builtin' ? source.block.tone : 'condition'
}

function beginLibraryDrag(
  source: LibraryDragSource,
  clientX: number,
  clientY: number,
  pointerId: number | null
) {
  blockDragState = { source, pointerId }
  draggingBlock.value = {
    label: libraryDragLabel(source),
    tone: libraryDragTone(source),
    x: clientX,
    y: clientY
  }
}

function updateBlockDrag(clientX: number, clientY: number) {
  if (!blockDragState) {
    return
  }

  draggingBlock.value = {
    label: libraryDragLabel(blockDragState.source),
    tone: libraryDragTone(blockDragState.source),
    x: clientX,
    y: clientY
  }
}

function finishBlockDrag(clientX: number, clientY: number) {
  if (!blockDragState) {
    return
  }

  if (blockDragState.source.type === 'builtin') {
    addBlockAtClientPoint(blockDragState.source.block, clientX, clientY)
  } else {
    addCustomBlockAtClientPoint(blockDragState.source.block, clientX, clientY)
  }
  draggingBlock.value = null
  blockDragState = null
}

function cancelBlockDrag() {
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

  if (isPointInsideFloatingLibrary(clientX, clientY)) {
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
    y: Math.round(position.y),
    params: createDefaultParams(block)
  })
}

function addCustomBlockAtClientPoint(block: CustomBlockTemplate, clientX: number, clientY: number) {
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

  if (isPointInsideFloatingLibrary(clientX, clientY)) {
    return
  }

  const templateNodes = block.template.nodes
    .map((node) => ({
      node,
      definition: blockDefinitions.find((definition) => definition.id === node.type)
    }))
    .filter((item): item is { node: StrategyNode; definition: BlockDefinition } =>
      Boolean(item.definition)
    )

  if (templateNodes.length === 0) {
    return
  }

  const minX = Math.min(...templateNodes.map((item) => item.node.x))
  const minY = Math.min(...templateNodes.map((item) => item.node.y))
  const point = screenToCanvasPoint(clientX, clientY, toCanvasRect(rect), transform)
  const position = snapBlockPosition(point)
  const seed = `${block.id}-${Date.now()}-${placedBlocks.value.length}`
  const nodeIdMap = new Map<string, string>()
  const nextBlocks = templateNodes.map((item, index) => {
    const nextId = `${item.node.type}-${seed}-${index}`
    nodeIdMap.set(item.node.id, nextId)
    return {
      id: nextId,
      blockId: item.definition.id,
      label: item.definition.label,
      tone: item.definition.tone,
      x: Math.round(position.x + item.node.x - minX),
      y: Math.round(position.y + item.node.y - minY),
      params: normalizeBlockParams(item.definition, item.node.params)
    }
  })

  const nextConnections = block.template.edges.reduce<Connection[]>((items, edge, index) => {
    const fromBlockId = nodeIdMap.get(edge.from)
    const toBlockId = nodeIdMap.get(edge.to)
    if (!fromBlockId || !toBlockId) {
      return items
    }

    items.push({
      id: `${fromBlockId}-${toBlockId}-${index}`,
      fromBlockId,
      toBlockId
    })
    return items
  }, [])

  placedBlocks.value.push(...nextBlocks)
  connections.value.push(...nextConnections)
}

function isPointInsideFloatingLibrary(clientX: number, clientY: number) {
  const libraryRect = libraryRef.value?.getBoundingClientRect()
  if (!libraryRect) {
    return false
  }

  return (
    clientX >= libraryRect.left &&
    clientX <= libraryRect.right &&
    clientY >= libraryRect.top &&
    clientY <= libraryRect.bottom
  )
}

function selectBlock(blockId: string) {
  if (ignoredPlacedBlockClickId === blockId) {
    ignoredPlacedBlockClickId = null
    return
  }

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

  if (inspectedBlockId.value === blockId) {
    inspectedBlockId.value = null
  }
}

function deleteConnection(connectionId: string) {
  connections.value = connections.value.filter((connection) => connection.id !== connectionId)
}

function openBlockInspector(blockId: string, event: MouseEvent) {
  event.preventDefault()
  contextMenu.value = null
  selectedBlockId.value = blockId
  inspectedBlockId.value = blockId
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

  deleteConnection(contextMenu.value.targetId)
  contextMenu.value = null
}

function closeContextMenu() {
  contextMenu.value = null
}

function deleteSelectedBlock() {
  if (!selectedBlock.value) {
    return
  }

  deleteBlock(selectedBlock.value.id)
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
  placedBlockDragState = {
    blockId: block.id,
    pointerId: event.pointerId,
    startPointer: screenToCanvasPoint(event.clientX, event.clientY, toCanvasRect(rect), transform),
    startBlock: { x: block.x, y: block.y },
    hasMoved: false
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
  if (
    Math.abs(currentPointer.x - placedBlockDragState.startPointer.x) > 2 ||
    Math.abs(currentPointer.y - placedBlockDragState.startPointer.y) > 2
  ) {
    placedBlockDragState.hasMoved = true
  }
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

  if (placedBlockDragState.hasMoved) {
    ignoredPlacedBlockClickId = placedBlockDragState.blockId
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
  beginLibraryDrag({ type: 'builtin', block }, event.clientX, event.clientY, event.pointerId)
  blockDragPointerTarget = event.currentTarget as HTMLElement
  blockDragPointerTarget.setPointerCapture?.(event.pointerId)
  window.addEventListener('pointermove', movePointerBlockDrag, true)
  window.addEventListener('pointerup', endPointerBlockDrag, true)
  window.addEventListener('pointercancel', cancelPointerBlockDrag, true)
  window.addEventListener('blur', cancelPointerBlockDrag)
}

function startPointerCustomBlockDrag(block: CustomBlockTemplate, event: PointerEvent) {
  if (event.button !== 0) {
    return
  }

  event.preventDefault()
  beginLibraryDrag({ type: 'custom', block }, event.clientX, event.clientY, event.pointerId)
  blockDragPointerTarget = event.currentTarget as HTMLElement
  blockDragPointerTarget.setPointerCapture?.(event.pointerId)
  window.addEventListener('pointermove', movePointerBlockDrag, true)
  window.addEventListener('pointerup', endPointerBlockDrag, true)
  window.addEventListener('pointercancel', cancelPointerBlockDrag, true)
  window.addEventListener('blur', cancelPointerBlockDrag)
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

  const pointerId = event.pointerId
  finishBlockDrag(event.clientX, event.clientY)
  releasePointerBlockDragCapture(pointerId)
  removePointerBlockDragListeners()
}

function cancelPointerBlockDrag(event?: Event) {
  if (!blockDragState || blockDragState.pointerId === null) {
    return
  }

  if (
    event &&
    'pointerId' in event &&
    blockDragState.pointerId !== (event as PointerEvent).pointerId
  ) {
    return
  }

  const pointerId = blockDragState.pointerId
  cancelBlockDrag()
  releasePointerBlockDragCapture(pointerId)
  removePointerBlockDragListeners()
}

function releasePointerBlockDragCapture(pointerId: number) {
  blockDragPointerTarget?.releasePointerCapture?.(pointerId)
  blockDragPointerTarget = null
}

function removePointerBlockDragListeners() {
  window.removeEventListener('pointermove', movePointerBlockDrag, true)
  window.removeEventListener('pointerup', endPointerBlockDrag, true)
  window.removeEventListener('pointercancel', cancelPointerBlockDrag, true)
  window.removeEventListener('blur', cancelPointerBlockDrag)
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

  cancelBlockDrag()
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
  beginLibraryDrag({ type: 'builtin', block }, event.clientX, event.clientY, null)
  window.addEventListener('mousemove', moveMouseBlockDrag)
  window.addEventListener('mouseup', endMouseBlockDrag)
  window.addEventListener('blur', cancelMouseBlockDrag)
}

function startMouseCustomBlockDrag(block: CustomBlockTemplate, event: MouseEvent) {
  if (event.button !== 0 || blockDragState) {
    return
  }

  event.preventDefault()
  beginLibraryDrag({ type: 'custom', block }, event.clientX, event.clientY, null)
  window.addEventListener('mousemove', moveMouseBlockDrag)
  window.addEventListener('mouseup', endMouseBlockDrag)
  window.addEventListener('blur', cancelMouseBlockDrag)
}

onMounted(() => {
  window.addEventListener('sts:builder-action', handleBuilderAction)
  loadWorkspaceStrategy()
  void loadCustomBlockLibrary()
})

watch(
  () => authStore.isAuthenticated,
  (isAuthenticated) => {
    if (isAuthenticated) {
      void loadCustomBlockLibrary()
      return
    }

    customBlockLibrary.value = []
    customBlockLibraryError.value = ''
  }
)

onBeforeUnmount(() => {
  window.removeEventListener('sts:builder-action', handleBuilderAction)
  removeMouseBlockDragListeners()
  removePointerBlockDragListeners()
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
    (event.target as HTMLElement).closest(
      [
        '.floating-block-library',
        '.block-inspector',
        '.strategy-review-modal',
        '.strategy-review-backdrop',
        '.canvas-block',
        '.canvas-controls'
      ].join(', ')
    )
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

function toggleLibraryCollapsed() {
  isLibraryCollapsed.value = !isLibraryCollapsed.value
}

function clearCanvas() {
  placedBlocks.value = []
  connections.value = []
  activeConnection.value = null
  selectedBlockId.value = null
  inspectedBlockId.value = null
  contextMenu.value = null
  placedBlockDragState = null
  currentStrategyId.value = null
  currentStrategyName.value = DEFAULT_STRATEGY_NAME
  strategySaveStatus.value = ''
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
        @contextmenu.prevent.stop="openBlockInspector(block.id, $event)"
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
      :class="`drag-preview--${draggingBlock.tone}`"
      :style="{ left: `${draggingBlock.x}px`, top: `${draggingBlock.y}px` }"
    >
      {{ draggingBlock.label }}
    </div>

    <p v-if="strategySaveStatus" class="strategy-save-status">{{ strategySaveStatus }}</p>

    <aside
      ref="libraryRef"
      class="block-library floating-block-library"
      :class="{ 'is-dragging': isDraggingLibrary, 'is-collapsed': isLibraryCollapsed }"
      :style="libraryStyle"
      aria-label="积木库"
      @wheel.stop
    >
      <header
        class="block-library-header"
        @pointerdown.stop="startLibraryDrag"
        @pointermove.stop="moveLibraryDrag"
        @pointerup.stop="endLibraryDrag"
        @pointercancel.stop="endLibraryDrag"
      >
        <h2>积木库</h2>
        <div class="block-library-header-actions">
          <span aria-hidden="true">••</span>
          <button
            v-if="!isLibraryCollapsed"
            class="custom-block-create-button"
            type="button"
            title="新建积木"
            aria-label="新建积木"
            @pointerdown.stop
            @click.stop="openCustomBlockModal"
          >
            +
          </button>
          <button
            class="block-library-collapse-toggle"
            :class="{ 'is-expand-arrow': isLibraryCollapsed }"
            type="button"
            :aria-label="isLibraryCollapsed ? '展开积木库' : '收起积木库'"
            @pointerdown.stop
            @click.stop="toggleLibraryCollapsed"
          ></button>
        </div>
      </header>
      <input
        v-if="!isLibraryCollapsed"
        v-model="blockSearchQuery"
        class="block-library-search"
        placeholder="搜索积木"
      />
      <nav v-if="!isLibraryCollapsed" class="block-library-groups">
        <section class="custom-block-library-section" aria-label="我的积木">
          <h3>我的积木</h3>
          <p v-if="!authStore.isAuthenticated" class="custom-block-library-hint">
            登录后可使用自己的积木
          </p>
          <p v-else-if="customBlockLibraryLoading" class="custom-block-library-hint">
            正在加载我的积木
          </p>
          <p v-else-if="customBlockLibraryError" class="custom-block-library-hint">
            {{ customBlockLibraryError }}
          </p>
          <p v-else-if="filteredCustomBlocks.length === 0" class="custom-block-library-hint">
            暂无匹配的自定义积木
          </p>
          <div v-else class="block-library-group-items">
            <button
              v-for="block in filteredCustomBlocks"
              :key="block.id"
              class="library-block custom-library-block library-block--condition"
              :data-custom-block-id="block.id"
              draggable="false"
              @pointerdown.stop="startPointerCustomBlockDrag(block, $event)"
              @pointermove.stop="movePointerBlockDrag"
              @pointerup.stop="endPointerBlockDrag"
              @pointercancel.stop="cancelPointerBlockDrag"
              @mousedown.stop="startMouseCustomBlockDrag(block, $event)"
            >
              <span>{{ block.name }}</span>
              <small>{{ block.template.nodes.length }}个</small>
            </button>
          </div>
        </section>
        <section
          v-for="group in filteredBlockGroups"
          :key="group.category"
          class="block-library-group"
        >
          <h3>{{ group.category }}</h3>
          <div class="block-library-group-items">
            <button
              v-for="block in group.blocks"
              :key="block.id"
              class="library-block"
              :class="`library-block--${block.tone}`"
              :data-block-id="block.id"
              draggable="false"
              @dragstart="startBlockDrag(block, $event)"
              @pointerdown.stop="startPointerBlockDrag(block, $event)"
              @pointermove.stop="movePointerBlockDrag"
              @pointerup.stop="endPointerBlockDrag"
              @pointercancel.stop="cancelPointerBlockDrag"
              @mousedown.stop="startMouseBlockDrag(block, $event)"
            >
              <span>{{ block.label }}</span>
              <small>{{ block.category }}</small>
            </button>
          </div>
        </section>
      </nav>
    </aside>

    <div
      v-if="isCustomBlockModalOpen"
      class="custom-block-modal-backdrop"
      @click.self="closeCustomBlockModal"
      @pointerdown.stop
      @wheel.stop
    >
      <aside
        class="custom-block-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="custom-block-modal-title"
        @click.stop
        @pointerdown.stop
        @contextmenu.stop
      >
        <header class="custom-block-modal-header">
          <div>
            <small>积木库</small>
            <h2 id="custom-block-modal-title">新建积木</h2>
          </div>
          <button
            class="custom-block-modal-close"
            type="button"
            aria-label="关闭新建积木"
            @click="closeCustomBlockModal"
          >
            ×
          </button>
        </header>

        <form class="custom-block-form" @submit.prevent="saveCustomBlockTemplate">
          <label>
            <span>积木名称</span>
            <input
              v-model="customBlockForm.name"
              class="custom-block-name-input"
              maxlength="80"
              placeholder="例如：突破买入模板"
            />
          </label>
          <label>
            <span>分类</span>
            <input
              v-model="customBlockForm.category"
              class="custom-block-category-input"
              maxlength="40"
              placeholder="例如：动作、风控、指标"
            />
          </label>
          <label>
            <span>描述</span>
            <textarea
              v-model="customBlockForm.description"
              class="custom-block-description-input"
              maxlength="500"
              rows="3"
              placeholder="说明这个积木适合什么场景"
            ></textarea>
          </label>
          <label>
            <span>标签</span>
            <input
              v-model="customBlockForm.tags"
              class="custom-block-tags-input"
              placeholder="用逗号分隔，例如：突破, 买入"
            />
          </label>
        </form>

        <p class="custom-block-status">{{ customBlockStatus }}</p>

        <footer class="custom-block-modal-footer">
          <button
            class="custom-block-cancel-button"
            type="button"
            @click="closeCustomBlockModal"
          >
            取消
          </button>
          <button
            class="custom-block-save-button"
            type="button"
            :disabled="validationIssues.length > 0 || isCustomBlockSaving"
            @click="saveCustomBlockTemplate"
          >
            {{ isCustomBlockSaving ? '保存中' : '保存到我的积木' }}
          </button>
        </footer>
      </aside>
    </div>

    <aside
      v-if="selectedBlock"
      class="block-inspector"
      aria-label="积木参数"
      @pointerdown.stop
      @click.stop
      @contextmenu.stop
    >
      <header>
        <div>
          <small>参数</small>
          <h2>{{ selectedBlock.label }}</h2>
        </div>
        <button type="button" aria-label="关闭参数面板" @click="inspectedBlockId = null">×</button>
      </header>

      <form @submit.prevent>
        <label v-for="field in selectedBlockFields" :key="field.key">
          <span>{{ field.label }}</span>
          <select
            v-if="field.type === 'select'"
            :data-param-key="field.key"
            :value="blockParamValue(selectedBlock, field)"
            @change="updateBlockParam(selectedBlock.id, field.key, $event)"
          >
            <option
              v-for="option in field.options"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
          <div v-else class="param-input-row">
            <input
              :data-param-key="field.key"
              :type="field.type"
              :min="field.min"
              :max="field.max"
              :step="field.step"
              :value="blockParamValue(selectedBlock, field)"
              @input="updateBlockParam(selectedBlock.id, field.key, $event)"
            />
            <small v-if="field.suffix">{{ field.suffix }}</small>
          </div>
        </label>
      </form>

      <footer class="block-inspector-actions">
        <button
          class="block-inspector-delete"
          type="button"
          @click="deleteSelectedBlock"
        >
          删除积木
        </button>
      </footer>
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
      <button
        class="clear-canvas-button"
        type="button"
        aria-label="清空画布"
        @click="clearCanvas"
      >
        清屏
      </button>
    </div>

    <div
      v-if="reviewModalMode"
      class="strategy-review-backdrop"
      @click.self="closeReviewModal"
      @pointerdown.stop
      @wheel.stop
    >
      <aside
        class="strategy-review-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="strategy-review-title"
        @click.stop
        @pointerdown.stop
        @contextmenu.stop
      >
        <header class="strategy-review-header">
          <div>
            <small>策略数据</small>
            <h2 id="strategy-review-title">{{ reviewModalTitle }}</h2>
          </div>
          <button
            class="strategy-review-close"
            type="button"
            aria-label="关闭策略预览"
            @click="closeReviewModal"
          >
            ×
          </button>
        </header>

        <div class="draft-actions">
          <button class="save-draft-button" type="button" @click="saveDraft">保存草稿</button>
          <button class="load-draft-button" type="button" @click="loadDraft">加载草稿</button>
        </div>
        <p class="draft-storage-hint">
          本地草稿保存在本机浏览器，不会同步到账户；清理浏览器数据后可能丢失。
        </p>
        <p class="draft-status">{{ draftStatus }}</p>

        <div class="strategy-review-body">
          <div class="strategy-review-column">
            <section class="validation-card" :class="{ 'is-ready': validationIssues.length === 0 }">
              <strong class="validation-summary">策略校验：{{ validationSummary }}</strong>
              <p v-if="validationIssues.length === 0" class="validation-empty">基础规则已通过</p>
              <ul v-else class="validation-issues">
                <li v-for="issue in validationIssues" :key="issue.id">{{ issue.message }}</li>
              </ul>
            </section>

            <section class="backtest-card" :class="{ 'is-ready': backtestIssues.length === 0 }">
              <strong class="backtest-summary">回测设置：{{ backtestSummary }}</strong>
              <form class="backtest-form" @submit.prevent>
                <label class="backtest-account-field">
                  <span>模拟账户</span>
                  <select
                    v-model="selectedSimulationAccountId"
                    data-backtest-key="simulationAccountId"
                    @change="applySelectedSimulationAccount"
                  >
                    <option value="">手动设置资金</option>
                    <option
                      v-for="account in simulationAccounts"
                      :key="account.id"
                      :value="String(account.id)"
                    >
                      {{ account.name }}
                    </option>
                  </select>
                </label>
                <label>
                  <span>市场</span>
                  <select
                    v-model="backtestSettings.market"
                    data-backtest-key="market"
                    :disabled="!!selectedSimulationAccountId"
                  >
                    <option value="A_SHARE">A股</option>
                    <option value="US_STOCK">美股</option>
                  </select>
                </label>
                <label>
                  <span>股票代码</span>
                  <input v-model="backtestSettings.symbol" data-backtest-key="symbol" />
                </label>
                <label>
                  <span>K线周期</span>
                  <select v-model="backtestSettings.timeframe" data-backtest-key="timeframe">
                    <option value="5m">5分钟</option>
                    <option value="1m">1分钟</option>
                  </select>
                </label>
                <label>
                  <span>开始日期</span>
                  <input
                    v-model="backtestSettings.startDate"
                    data-backtest-key="startDate"
                    type="date"
                  />
                </label>
                <label>
                  <span>结束日期</span>
                  <input
                    v-model="backtestSettings.endDate"
                    data-backtest-key="endDate"
                    type="date"
                  />
                </label>
                <label>
                  <span>初始资金</span>
                  <input
                    v-model="backtestSettings.initialCash"
                    data-backtest-key="initialCash"
                    type="number"
                    min="1"
                    step="1000"
                    :disabled="!!selectedSimulationAccountId"
                  />
                </label>
              </form>
              <p v-if="isLoadingSimulationAccounts" class="backtest-account-status">
                正在加载模拟账户
              </p>
              <p v-else-if="simulationAccountError" class="backtest-run-error">
                {{ simulationAccountError }}
              </p>
              <p v-if="backtestIssues.length === 0" class="backtest-empty">回测配置已准备</p>
              <ul v-else class="backtest-issues">
                <li v-for="issue in backtestIssues" :key="issue.id">{{ issue.message }}</li>
              </ul>
            </section>

            <section v-if="backtestRunResult || backtestRunError" class="backtest-result-card">
              <template v-if="backtestRunResult">
                <header class="backtest-result-header">
                  <strong>回测结果</strong>
                  <button
                    v-if="authStore.isAuthenticated"
                    class="backtest-space-button"
                    type="button"
                    @click="openPersonalBacktests"
                  >
                    查看我的回测
                  </button>
                </header>
                <p v-if="backtestPersistStatus" class="backtest-persist-status">
                  {{ backtestPersistStatus }}
                </p>
                <div class="backtest-metrics">
                  <span>
                    <small>总收益率</small>
                    <b>{{ backtestRunResult.summary.totalReturnPercent }}%</b>
                  </span>
                  <span>
                    <small>最大回撤</small>
                    <b>{{ backtestRunResult.summary.maxDrawdownPercent }}%</b>
                  </span>
                  <span>
                    <small>胜率</small>
                    <b>{{ backtestRunResult.summary.winRatePercent }}%</b>
                  </span>
                  <span>
                    <small>期末资产</small>
                    <b>{{ backtestRunResult.summary.endingEquity }}</b>
                  </span>
                </div>
                <table class="backtest-trades">
                  <thead>
                    <tr>
                      <th>时间</th>
                      <th>方向</th>
                      <th>价格</th>
                      <th>数量</th>
                      <th>原因</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="trade in backtestRunResult.trades" :key="`${trade.time}-${trade.side}`">
                      <td>{{ trade.time }}</td>
                      <td>{{ trade.side }}</td>
                      <td>{{ trade.price }}</td>
                      <td>{{ trade.quantity }}</td>
                      <td>{{ trade.reason }}</td>
                    </tr>
                  </tbody>
                </table>
              </template>
              <p v-else class="backtest-run-error">{{ backtestRunError }}</p>
            </section>
          </div>

          <div class="strategy-review-column">
            <section class="review-preview-section">
              <strong>回测配置 JSON</strong>
              <pre class="backtest-config-preview">{{ backtestJson }}</pre>
            </section>
            <section class="review-preview-section">
              <strong>策略 JSON</strong>
              <pre class="strategy-json-preview">{{ strategyJson }}</pre>
            </section>
          </div>
        </div>

        <footer class="strategy-review-footer">
          <button class="review-secondary-button" type="button" @click="closeReviewModal">
            继续搭建
          </button>
          <button
            class="review-primary-button"
            type="button"
            :disabled="reviewPrimaryDisabled || isBacktestRunning"
            @click="handleReviewPrimaryAction"
          >
            {{ isBacktestRunning ? '回测中' : reviewPrimaryLabel }}
          </button>
        </footer>
      </aside>
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
        删除连接
      </button>
    </div>
  </section>
</template>
