<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiClient } from '../api/http'
import { useAuthStore } from '../stores/auth'
import {
  useStrategyWorkspaceStore,
  type BacktestConfigPayload,
  type SavedStrategy,
  type StrategyDraftPayload
} from '../stores/strategyWorkspace'

type SpaceTab = 'overview' | 'strategies' | 'accounts' | 'backtests'

interface StrategyListResponse {
  items: SavedStrategy[]
  total: number
  page: number
  pageSize: number
}

interface BacktestListItem {
  id: number
  runId: string
  status: string
  market: 'A_SHARE' | 'US_STOCK'
  symbol: string
  timeframe: '5m' | '1m'
  startDate: string
  endDate: string
  totalReturnPercent: number
  maxDrawdownPercent: number
  winRatePercent: number
  endingEquity: number
  tradeCount: number
  simulationAccountId?: number | null
  simulationAccountName?: string | null
  createdAt: string
}

interface BacktestListResponse {
  items: BacktestListItem[]
  total: number
  page: number
  pageSize: number
}

interface SimulationAccount {
  id: number
  ownerId: number
  name: string
  description: string | null
  market: 'A_SHARE' | 'US_STOCK'
  initialCash: number
  createdAt: string
  updatedAt: string
}

interface SimulationAccountListResponse {
  items: SimulationAccount[]
  total: number
  page: number
  pageSize: number
}

interface BacktestTrade {
  time: string
  side: 'BUY' | 'SELL'
  price: number
  quantity: number
  reason: string
}

interface EquityPoint {
  time: string
  equity: number
}

interface ChartDataPoint {
  time: string
  value: number
}

interface ChartCoordinate extends ChartDataPoint {
  x: number
  y: number
}

interface BacktestChartModel {
  points: string
  coordinates: ChartCoordinate[]
  startLabel: string
  endLabel: string
  minLabel: string
  maxLabel: string
  latestLabel: string
}

interface TradeMarker {
  id: string
  x: number
  y: number
  side: BacktestTrade['side']
  sideLabel: string
  testId: string
  label: string
}

interface TradeReviewItem {
  id: string
  time: string
  side: BacktestTrade['side']
  sideLabel: string
  quantityText: string
  priceText: string
  reason: string
}

interface SnapshotField {
  label: string
  value: string
}

interface StrategyBlockSummary {
  label: string
  count: number
}

interface BacktestDetail extends BacktestListItem {
  strategy: StrategyDraftPayload
  config: BacktestConfigPayload & {
    simulationAccountId?: number | null
  }
  summary: {
    totalReturnPercent: number
    maxDrawdownPercent: number
    winRatePercent: number
    endingEquity: number
    tradeCount: number
  }
  trades: BacktestTrade[]
  equityCurve: EquityPoint[]
}

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const workspaceStore = useStrategyWorkspaceStore()
const activeTab = ref<SpaceTab>(spaceTabFromQuery(route.query.tab))
const strategies = ref<SavedStrategy[]>([])
const accounts = ref<SimulationAccount[]>([])
const backtests = ref<BacktestListItem[]>([])
const selectedBacktest = ref<BacktestDetail | null>(null)
const strategyKeyword = ref('')
const accountKeyword = ref('')
const backtestKeyword = ref('')
const strategyPage = ref(1)
const accountPage = ref(1)
const backtestPage = ref(1)
const pageSize = 10
const strategyTotal = ref(0)
const accountTotal = ref(0)
const backtestTotal = ref(0)
const strategyLoading = ref(false)
const accountLoading = ref(false)
const backtestLoading = ref(false)
const backtestDetailLoading = ref(false)
const strategyError = ref('')
const accountError = ref('')
const backtestError = ref('')
const editingAccountId = ref<number | null>(null)
const accountForm = ref({
  name: '',
  description: '',
  market: 'A_SHARE' as SimulationAccount['market'],
  initialCash: 100000
})
const chartWidth = 320
const chartHeight = 120
const chartPadding = 16

function spaceTabFromQuery(tab: unknown): SpaceTab {
  const value = Array.isArray(tab) ? tab[0] : tab
  if (
    value === 'overview' ||
    value === 'strategies' ||
    value === 'accounts' ||
    value === 'backtests'
  ) {
    return value
  }
  return 'overview'
}

const bestBacktest = computed(() =>
  backtests.value.reduce<BacktestListItem | null>((best, item) => {
    if (!best || item.totalReturnPercent > best.totalReturnPercent) {
      return item
    }
    return best
  }, null)
)

const lowestDrawdownBacktest = computed(() =>
  backtests.value.reduce<BacktestListItem | null>((best, item) => {
    if (!best || item.maxDrawdownPercent < best.maxDrawdownPercent) {
      return item
    }
    return best
  }, null)
)

const latestStrategy = computed(() => strategies.value[0] ?? null)
const latestAccount = computed(() => accounts.value[0] ?? null)
const latestBacktest = computed(() => backtests.value[0] ?? null)
const strategyTotalPages = computed(() => Math.max(1, Math.ceil(strategyTotal.value / pageSize)))
const accountTotalPages = computed(() => Math.max(1, Math.ceil(accountTotal.value / pageSize)))
const backtestTotalPages = computed(() => Math.max(1, Math.ceil(backtestTotal.value / pageSize)))
const selectedEquityChart = computed(() => {
  const curve = selectedBacktest.value?.equityCurve ?? []
  return buildChartModel(
    curve.map((point) => ({ time: point.time, value: point.equity })),
    {
      highValueAtTop: true,
      formatLabel: (value) => formatAmount(value)
    }
  )
})
const selectedDrawdownChart = computed(() => {
  const curve = selectedBacktest.value?.equityCurve ?? []
  let peak = 0
  const drawdownPoints = curve.map<ChartDataPoint>((point) => {
    peak = Math.max(peak, point.equity)
    const drawdown = peak > 0 ? ((peak - point.equity) / peak) * 100 : 0
    return {
      time: point.time,
      value: drawdown
    }
  })

  return buildChartModel(drawdownPoints, {
    highValueAtTop: false,
    minValue: 0,
    formatLabel: (value) => formatPercent(value)
  })
})
const selectedEquityTradeMarkers = computed<TradeMarker[]>(() => {
  if (!selectedBacktest.value || !selectedEquityChart.value) {
    return []
  }

  const coordinateByTime = new Map(
    selectedEquityChart.value.coordinates.map((coordinate) => [coordinate.time, coordinate])
  )
  return selectedBacktest.value.trades.flatMap((trade, index) => {
    const coordinate = coordinateByTime.get(trade.time)
    if (!coordinate) {
      return []
    }
    const sideLabel = formatTradeSide(trade.side)
    return [
      {
        id: `${trade.time}-${trade.side}-${index}`,
        x: coordinate.x,
        y: coordinate.y,
        side: trade.side,
        sideLabel,
        testId: `trade-marker-${trade.side.toLowerCase()}`,
        label: `${sideLabel} ${trade.quantity} 股，价格 ${formatAmount(trade.price)}，${trade.reason}`
      }
    ]
  })
})
const selectedTradeReviews = computed<TradeReviewItem[]>(() =>
  (selectedBacktest.value?.trades ?? []).map((trade, index) => {
    const sideLabel = formatTradeSide(trade.side)
    return {
      id: `${trade.time}-${trade.side}-${index}`,
      time: trade.time,
      side: trade.side,
      sideLabel,
      quantityText: `${sideLabel} ${trade.quantity} 股`,
      priceText: `${formatAmount(trade.price)} / 股`,
      reason: trade.reason
    }
  })
)
const selectedBacktestSnapshotFields = computed<SnapshotField[]>(() => {
  const backtest = selectedBacktest.value
  if (!backtest) {
    return []
  }

  return [
    { label: '市场', value: formatMarket(backtest.config.market) },
    { label: '股票', value: backtest.config.symbol },
    { label: '周期', value: formatTimeframe(backtest.config.timeframe) },
    { label: '区间', value: `${backtest.config.startDate} 至 ${backtest.config.endDate}` },
    { label: '初始资金', value: formatAmount(backtest.config.initialCash) },
    { label: '模拟账户', value: backtest.simulationAccountName ?? '未绑定' }
  ]
})
const selectedStrategyBlockSummaries = computed<StrategyBlockSummary[]>(() => {
  const nodes = selectedBacktest.value?.strategy.nodes ?? []
  const counts = nodes.reduce<Map<string, StrategyBlockSummary>>((summary, node) => {
    const label = node.label || node.type
    const current = summary.get(label) ?? { label, count: 0 }
    current.count += 1
    summary.set(label, current)
    return summary
  }, new Map())
  return Array.from(counts.values()).sort((left, right) => left.label.localeCompare(right.label))
})

async function loadStrategies() {
  strategyLoading.value = true
  strategyError.value = ''
  try {
    const response = await apiClient.get<StrategyListResponse>('/strategies', {
      params: {
        keyword: strategyKeyword.value.trim(),
        page: strategyPage.value,
        pageSize
      }
    })
    strategies.value = response.data.items
    strategyTotal.value = response.data.total
  } catch {
    strategyError.value = '策略列表加载失败，请确认已登录'
  } finally {
    strategyLoading.value = false
  }
}

async function searchStrategies() {
  strategyPage.value = 1
  await loadStrategies()
}

async function loadAccounts() {
  accountLoading.value = true
  accountError.value = ''
  try {
    const response = await apiClient.get<SimulationAccountListResponse>('/simulation-accounts', {
      params: {
        keyword: accountKeyword.value.trim(),
        page: accountPage.value,
        pageSize
      }
    })
    accounts.value = response.data.items
    accountTotal.value = response.data.total
  } catch {
    accountError.value = '模拟账户加载失败，请确认已登录'
  } finally {
    accountLoading.value = false
  }
}

async function searchAccounts() {
  accountPage.value = 1
  await loadAccounts()
}

async function loadBacktests() {
  backtestLoading.value = true
  backtestError.value = ''
  try {
    const response = await apiClient.get<BacktestListResponse>('/backtests', {
      params: {
        keyword: backtestKeyword.value.trim(),
        page: backtestPage.value,
        pageSize
      }
    })
    backtests.value = response.data.items
    backtestTotal.value = response.data.total
    if (selectedBacktest.value) {
      const stillVisible = response.data.items.some((item) => item.id === selectedBacktest.value?.id)
      if (!stillVisible) {
        selectedBacktest.value = null
      }
    }
  } catch {
    backtestError.value = '回测记录加载失败，请确认已登录'
  } finally {
    backtestLoading.value = false
  }
}

async function loadSpaceData() {
  await Promise.all([loadStrategies(), loadAccounts(), loadBacktests()])
}

async function searchBacktests() {
  backtestPage.value = 1
  selectedBacktest.value = null
  await loadBacktests()
}

async function searchActiveTab() {
  if (activeTab.value === 'strategies') {
    await searchStrategies()
    return
  }
  if (activeTab.value === 'accounts') {
    await searchAccounts()
    return
  }
  if (activeTab.value === 'backtests') {
    await searchBacktests()
  }
}

function openStrategy(strategy: SavedStrategy) {
  workspaceStore.openStrategy(strategy)
  void router.push('/')
}

async function deleteStrategy(strategy: SavedStrategy) {
  await apiClient.delete(`/strategies/${strategy.id}`)
  await loadStrategies()
}

function resetAccountForm() {
  editingAccountId.value = null
  accountForm.value = {
    name: '',
    description: '',
    market: 'A_SHARE',
    initialCash: 100000
  }
}

async function submitAccount() {
  const payload = {
    name: accountForm.value.name.trim(),
    description: accountForm.value.description.trim() || null,
    market: accountForm.value.market,
    initialCash: Number(accountForm.value.initialCash)
  }

  if (editingAccountId.value) {
    await apiClient.put(`/simulation-accounts/${editingAccountId.value}`, payload)
  } else {
    await apiClient.post('/simulation-accounts', payload)
  }
  await loadAccounts()
  resetAccountForm()
}

function editAccount(account: SimulationAccount) {
  editingAccountId.value = account.id
  accountForm.value = {
    name: account.name,
    description: account.description ?? '',
    market: account.market,
    initialCash: account.initialCash
  }
}

async function deleteAccount(account: SimulationAccount) {
  await apiClient.delete(`/simulation-accounts/${account.id}`)
  if (editingAccountId.value === account.id) {
    resetAccountForm()
  }
  await loadAccounts()
}

async function openBacktest(backtest: BacktestListItem) {
  if (isSelectedBacktest(backtest) && !backtestDetailLoading.value) {
    closeBacktestDetail()
    return
  }

  backtestDetailLoading.value = true
  backtestError.value = ''
  try {
    const response = await apiClient.get<BacktestDetail>(`/backtests/${backtest.id}`)
    selectedBacktest.value = response.data
  } catch {
    backtestError.value = '回测详情加载失败'
  } finally {
    backtestDetailLoading.value = false
  }
}

function isSelectedBacktest(backtest: BacktestListItem) {
  return selectedBacktest.value?.id === backtest.id
}

function closeBacktestDetail() {
  selectedBacktest.value = null
  backtestError.value = ''
}

function replaySelectedBacktestStrategy() {
  const backtest = selectedBacktest.value
  if (!backtest) {
    return
  }

  workspaceStore.openBacktestSnapshot({
    name: `回测复盘：${backtest.symbol} ${formatTimeframe(backtest.timeframe)}`,
    description: `来自回测记录 ${backtest.runId}`,
    strategy: backtest.strategy,
    backtestConfig: {
      market: backtest.config.market,
      symbol: backtest.config.symbol,
      timeframe: backtest.config.timeframe,
      startDate: backtest.config.startDate,
      endDate: backtest.config.endDate,
      initialCash: backtest.config.initialCash,
      ...(backtest.simulationAccountId
        ? { simulationAccountId: backtest.simulationAccountId }
        : {})
    },
    statusMessage: `已载入回测策略快照：${backtest.symbol}`
  })
  void router.push('/')
}

async function changeStrategyPage(nextPage: number) {
  if (nextPage < 1 || nextPage > strategyTotalPages.value || nextPage === strategyPage.value) {
    return
  }
  strategyPage.value = nextPage
  await loadStrategies()
}

async function changeAccountPage(nextPage: number) {
  if (nextPage < 1 || nextPage > accountTotalPages.value || nextPage === accountPage.value) {
    return
  }
  accountPage.value = nextPage
  await loadAccounts()
}

async function changeBacktestPage(nextPage: number) {
  if (nextPage < 1 || nextPage > backtestTotalPages.value || nextPage === backtestPage.value) {
    return
  }
  backtestPage.value = nextPage
  selectedBacktest.value = null
  await loadBacktests()
}

function formatMarket(market: BacktestListItem['market'] | undefined) {
  if (market === 'US_STOCK') {
    return '美股'
  }
  return 'A股'
}

function formatTimeframe(timeframe: string | undefined) {
  return timeframe === '1m' ? '1分钟' : '5分钟'
}

function formatPercent(value: number | undefined) {
  return `${Number(value ?? 0)
    .toFixed(2)
    .replace(/\.00$/, '')
    .replace(/(\.\d)0$/, '$1')}%`
}

function formatAmount(value: number | undefined) {
  return Number(value ?? 0).toLocaleString('zh-CN', {
    maximumFractionDigits: 2
  })
}

function formatDate(value: string | undefined) {
  return value ? value.slice(0, 10) : '-'
}

function formatTradeSide(side: BacktestTrade['side']) {
  return side === 'BUY' ? '买入' : '卖出'
}

function buildChartModel(
  points: ChartDataPoint[],
  options: {
    highValueAtTop: boolean
    formatLabel: (value: number) => string
    minValue?: number
    maxValue?: number
  }
): BacktestChartModel | null {
  if (points.length === 0) {
    return null
  }

  const values = points.map((point) => point.value)
  const minValue = options.minValue ?? Math.min(...values)
  const maxValue = options.maxValue ?? Math.max(...values)
  const range = maxValue - minValue
  const coordinates = points.map<ChartCoordinate>((point, index) => {
    const x =
      points.length === 1
        ? chartWidth / 2
        : chartPadding + (index / (points.length - 1)) * (chartWidth - chartPadding * 2)
    const normalized = range === 0 ? 0.5 : (point.value - minValue) / range
    const yRatio = options.highValueAtTop ? 1 - normalized : normalized
    const y = chartPadding + yRatio * (chartHeight - chartPadding * 2)
    return {
      ...point,
      x,
      y
    }
  })

  return {
    points: coordinates.map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(' '),
    coordinates,
    startLabel: points[0].time,
    endLabel: points[points.length - 1].time,
    minLabel: options.formatLabel(minValue),
    maxLabel: options.formatLabel(maxValue),
    latestLabel: options.formatLabel(points[points.length - 1].value)
  }
}

watch(
  () => authStore.isAuthenticated,
  (isAuthenticated, wasAuthenticated) => {
    if (isAuthenticated && !wasAuthenticated) {
      void loadSpaceData()
    }
  }
)

watch(
  () => route.query.tab,
  (tab) => {
    activeTab.value = spaceTabFromQuery(tab)
  }
)

onMounted(() => {
  void loadSpaceData()
})
</script>

<template>
  <section class="page-panel personal-space">
    <header class="space-header">
      <div>
        <h1>个人空间</h1>
        <p>策略资产、回测记录与个人沉淀</p>
      </div>
      <form v-if="activeTab !== 'overview'" class="space-search" @submit.prevent="searchActiveTab">
        <input
          v-if="activeTab === 'strategies'"
          v-model="strategyKeyword"
          placeholder="搜索策略"
        />
        <input
          v-else-if="activeTab === 'accounts'"
          v-model="accountKeyword"
          placeholder="搜索账户、市场"
        />
        <input
          v-else
          v-model="backtestKeyword"
          placeholder="搜索股票、市场、周期"
        />
        <button type="submit">搜索</button>
      </form>
    </header>

    <nav class="space-tabs" aria-label="个人空间页面">
      <button
        type="button"
        data-space-tab="overview"
        :class="{ 'is-active': activeTab === 'overview' }"
        @click="activeTab = 'overview'"
      >
        概览
      </button>
      <button
        type="button"
        data-space-tab="strategies"
        :class="{ 'is-active': activeTab === 'strategies' }"
        @click="activeTab = 'strategies'"
      >
        我的策略
      </button>
      <button
        type="button"
        data-space-tab="accounts"
        :class="{ 'is-active': activeTab === 'accounts' }"
        @click="activeTab = 'accounts'"
      >
        模拟账户
      </button>
      <button
        type="button"
        data-space-tab="backtests"
        :class="{ 'is-active': activeTab === 'backtests' }"
        @click="activeTab = 'backtests'"
      >
        我的回测
      </button>
    </nav>

    <section v-if="activeTab === 'overview'" class="space-overview">
      <div class="space-overview-grid">
        <article class="space-metric">
          <small>策略总数</small>
          <strong>{{ strategyTotal }}</strong>
        </article>
        <article class="space-metric">
          <small>回测总数</small>
          <strong>{{ backtestTotal }}</strong>
        </article>
        <article class="space-metric">
          <small>账户总数</small>
          <strong>{{ accountTotal }}</strong>
        </article>
        <article class="space-metric">
          <small>最佳收益</small>
          <strong>{{ formatPercent(bestBacktest?.totalReturnPercent) }}</strong>
        </article>
        <article class="space-metric">
          <small>最低回撤</small>
          <strong>{{ formatPercent(lowestDrawdownBacktest?.maxDrawdownPercent) }}</strong>
        </article>
      </div>

      <div class="space-overview-lanes">
        <article class="space-lane">
          <div>
            <small>最近策略</small>
            <h2>{{ latestStrategy?.name || '暂无策略' }}</h2>
            <p v-if="latestStrategy">
              {{ latestStrategy.backtestConfig?.symbol || '未设置股票' }}
              ·
              {{ formatTimeframe(latestStrategy.backtestConfig?.timeframe) }}
            </p>
          </div>
          <button
            v-if="latestStrategy"
            class="strategy-open-button"
            type="button"
            @click="openStrategy(latestStrategy)"
          >
            打开
          </button>
        </article>
        <article class="space-lane">
          <div>
            <small>最近账户</small>
            <h2>{{ latestAccount?.name || '暂无账户' }}</h2>
            <p v-if="latestAccount">
              {{ formatMarket(latestAccount.market) }}
              ·
              初始资金 {{ latestAccount.initialCash }}
            </p>
          </div>
          <button
            v-if="latestAccount"
            type="button"
            @click="activeTab = 'accounts'"
          >
            管理
          </button>
        </article>
        <article class="space-lane">
          <div>
            <small>最近回测</small>
            <h2>{{ latestBacktest?.symbol || '暂无回测' }}</h2>
            <p v-if="latestBacktest">
              {{ formatMarket(latestBacktest.market) }}
              ·
              {{ formatTimeframe(latestBacktest.timeframe) }}
              ·
              {{ formatPercent(latestBacktest.totalReturnPercent) }}
            </p>
          </div>
          <button
            v-if="latestBacktest"
            class="backtest-open-button"
            type="button"
            @click="openBacktest(latestBacktest)"
          >
            查看
          </button>
        </article>
      </div>

      <aside v-if="selectedBacktest" class="space-detail-panel">
        <strong>回测详情</strong>
        <span>{{ selectedBacktest.symbol }} · {{ formatPercent(selectedBacktest.summary.totalReturnPercent) }}</span>
      </aside>
    </section>

    <section v-else-if="activeTab === 'strategies'" class="space-section">
      <p v-if="strategyError" class="form-error">{{ strategyError }}</p>
      <p v-else-if="strategyLoading" class="space-muted">正在加载策略</p>
      <p v-else-if="strategies.length === 0" class="space-muted">暂无已保存策略</p>

      <div v-else class="strategy-list">
        <article v-for="strategy in strategies" :key="strategy.id" class="strategy-item">
          <div>
            <h2>{{ strategy.name }}</h2>
            <p>{{ strategy.description || '无描述' }}</p>
            <small>
              {{ strategy.backtestConfig?.symbol || '未设置股票' }}
              ·
              {{ formatTimeframe(strategy.backtestConfig?.timeframe) }}
              ·
              更新于 {{ formatDate(strategy.updatedAt) }}
            </small>
          </div>
          <div class="strategy-item-actions">
            <button class="strategy-open-button" type="button" @click="openStrategy(strategy)">
              打开
            </button>
            <button class="strategy-delete-button" type="button" @click="deleteStrategy(strategy)">
              删除
            </button>
          </div>
        </article>
      </div>

      <footer class="space-footer">
        <span>共 {{ strategyTotal }} 条策略</span>
        <div class="space-pagination">
          <button
            type="button"
            data-pagination="strategies-prev"
            :disabled="strategyPage <= 1"
            @click="changeStrategyPage(strategyPage - 1)"
          >
            上一页
          </button>
          <span>第 {{ strategyPage }} / {{ strategyTotalPages }} 页</span>
          <button
            type="button"
            data-pagination="strategies-next"
            :disabled="strategyPage >= strategyTotalPages"
            @click="changeStrategyPage(strategyPage + 1)"
          >
            下一页
          </button>
        </div>
      </footer>
    </section>

    <section v-else-if="activeTab === 'accounts'" class="space-section">
      <p v-if="accountError" class="form-error">{{ accountError }}</p>

      <div class="account-layout">
        <form class="account-form" @submit.prevent="submitAccount">
          <strong>{{ editingAccountId ? '编辑模拟账户' : '创建模拟账户' }}</strong>
          <label>
            <span>账户名称</span>
            <input
              v-model="accountForm.name"
              class="account-name-input"
              required
              maxlength="80"
              placeholder="例如 A股日内账户"
            />
          </label>
          <label>
            <span>市场</span>
            <select v-model="accountForm.market" class="account-market-select">
              <option value="A_SHARE">A股</option>
              <option value="US_STOCK">美股</option>
            </select>
          </label>
          <label>
            <span>初始资金</span>
            <input
              v-model.number="accountForm.initialCash"
              class="account-cash-input"
              type="number"
              min="1"
              required
            />
          </label>
          <label>
            <span>备注</span>
            <textarea
              v-model="accountForm.description"
              class="account-description-input"
              maxlength="500"
              placeholder="用途、周期或资金规则"
            />
          </label>
          <div class="account-form-actions">
            <button class="account-submit-button" type="submit" @click.prevent="submitAccount">
              {{ editingAccountId ? '保存修改' : '创建账户' }}
            </button>
            <button v-if="editingAccountId" type="button" @click="resetAccountForm">
              取消
            </button>
          </div>
        </form>

        <div class="account-list">
          <p v-if="accountLoading" class="space-muted">正在加载模拟账户</p>
          <p v-else-if="accounts.length === 0" class="space-muted">暂无模拟账户</p>
          <article v-for="account in accounts" v-else :key="account.id" class="account-item">
            <div>
              <h2>{{ account.name }}</h2>
              <p>{{ account.description || '无描述' }}</p>
              <small>
                {{ formatMarket(account.market) }}
                ·
                初始资金 {{ account.initialCash }}
                ·
                更新于 {{ formatDate(account.updatedAt) }}
              </small>
            </div>
            <div class="strategy-item-actions">
              <button class="account-edit-button" type="button" @click="editAccount(account)">
                编辑
              </button>
              <button class="account-delete-button" type="button" @click="deleteAccount(account)">
                删除
              </button>
            </div>
          </article>
        </div>
      </div>

      <footer class="space-footer">
        <span>共 {{ accountTotal }} 个账户</span>
        <div class="space-pagination">
          <button
            type="button"
            data-pagination="accounts-prev"
            :disabled="accountPage <= 1"
            @click="changeAccountPage(accountPage - 1)"
          >
            上一页
          </button>
          <span>第 {{ accountPage }} / {{ accountTotalPages }} 页</span>
          <button
            type="button"
            data-pagination="accounts-next"
            :disabled="accountPage >= accountTotalPages"
            @click="changeAccountPage(accountPage + 1)"
          >
            下一页
          </button>
        </div>
      </footer>
    </section>

    <section v-else class="space-section space-backtests">
      <p v-if="backtestError" class="form-error">{{ backtestError }}</p>
      <p v-else-if="backtestLoading" class="space-muted">正在加载回测</p>
      <p v-else-if="backtests.length === 0" class="space-muted">暂无回测记录</p>

      <div v-else class="backtest-layout">
        <div class="backtest-list">
          <article
            v-for="backtest in backtests"
            :key="backtest.id"
            class="backtest-item"
            :class="{ 'is-selected': isSelectedBacktest(backtest) }"
          >
            <div>
              <h2>{{ backtest.symbol }}</h2>
              <p>
                {{ formatMarket(backtest.market) }}
                ·
                {{ formatTimeframe(backtest.timeframe) }}
                ·
                {{ backtest.startDate }} 至 {{ backtest.endDate }}
              </p>
              <small>
                收益 {{ formatPercent(backtest.totalReturnPercent) }}
                ·
                最大回撤 {{ formatPercent(backtest.maxDrawdownPercent) }}
                ·
                {{ backtest.tradeCount }} 笔
                <template v-if="backtest.simulationAccountName">
                  ·
                  使用账户 {{ backtest.simulationAccountName }}
                </template>
              </small>
            </div>
            <button class="backtest-open-button" type="button" @click="openBacktest(backtest)">
              {{ isSelectedBacktest(backtest) ? '收起' : '查看' }}
            </button>
          </article>
        </div>

        <aside class="space-detail-panel" :aria-busy="backtestDetailLoading">
          <template v-if="selectedBacktest">
            <header class="detail-panel-header">
              <strong>回测详情</strong>
              <button class="backtest-close-button" type="button" @click="closeBacktestDetail">
                收起
              </button>
            </header>
            <div class="backtest-detail-metrics">
              <span>
                <small>收益</small>
                <b>{{ formatPercent(selectedBacktest.summary.totalReturnPercent) }}</b>
              </span>
              <span>
                <small>回撤</small>
                <b>{{ formatPercent(selectedBacktest.summary.maxDrawdownPercent) }}</b>
              </span>
              <span>
                <small>资产</small>
                <b>{{ selectedBacktest.summary.endingEquity }}</b>
              </span>
            </div>
            <p v-if="selectedBacktest.simulationAccountName" class="space-muted">
              账户 {{ selectedBacktest.simulationAccountName }}
            </p>
            <section class="backtest-snapshot">
              <header>
                <strong>回测快照</strong>
                <div class="snapshot-header-actions">
                  <small>策略积木 {{ selectedBacktest.strategy.nodes.length }} 个</small>
                  <button
                    class="backtest-replay-button"
                    type="button"
                    @click="replaySelectedBacktestStrategy"
                  >
                    复盘策略
                  </button>
                </div>
              </header>
              <dl class="snapshot-grid">
                <div v-for="field in selectedBacktestSnapshotFields" :key="field.label">
                  <dt>{{ field.label }}</dt>
                  <dd>{{ field.value }}</dd>
                </div>
              </dl>
              <div class="strategy-block-summary" aria-label="策略积木摘要">
                <span>策略积木</span>
                <ul>
                  <li
                    v-for="summary in selectedStrategyBlockSummaries"
                    :key="summary.label"
                  >
                    {{ summary.label }} x{{ summary.count }}
                  </li>
                </ul>
              </div>
            </section>
            <div
              v-if="selectedEquityChart || selectedDrawdownChart"
              class="backtest-chart-grid"
            >
              <article v-if="selectedEquityChart" class="backtest-chart-card">
                <header>
                  <span>权益曲线</span>
                  <small>{{ selectedEquityChart.latestLabel }}</small>
                </header>
                <svg
                  class="backtest-line-chart"
                  viewBox="0 0 320 120"
                  role="img"
                  aria-label="权益曲线"
                >
                  <line x1="16" y1="16" x2="304" y2="16" />
                  <line x1="16" y1="60" x2="304" y2="60" />
                  <line x1="16" y1="104" x2="304" y2="104" />
                  <polyline
                    data-testid="equity-chart-line"
                    class="backtest-line-chart__line backtest-line-chart__line--equity"
                    :points="selectedEquityChart.points"
                  />
                  <g
                    v-for="marker in selectedEquityTradeMarkers"
                    :key="marker.id"
                    class="trade-marker"
                    :class="marker.side === 'BUY' ? 'trade-marker--buy' : 'trade-marker--sell'"
                    :data-testid="marker.testId"
                    :transform="`translate(${marker.x.toFixed(1)} ${marker.y.toFixed(1)})`"
                    :aria-label="marker.label"
                  >
                    <title>{{ marker.label }}</title>
                    <circle r="5" />
                    <text y="-9" text-anchor="middle">{{ marker.sideLabel }}</text>
                  </g>
                </svg>
                <footer>
                  <span>{{ selectedEquityChart.startLabel }}</span>
                  <span>{{ selectedEquityChart.endLabel }}</span>
                </footer>
                <small>
                  低 {{ selectedEquityChart.minLabel }} · 高 {{ selectedEquityChart.maxLabel }}
                </small>
              </article>

              <article v-if="selectedDrawdownChart" class="backtest-chart-card">
                <header>
                  <span>回撤曲线</span>
                  <small>{{ selectedDrawdownChart.latestLabel }}</small>
                </header>
                <svg
                  class="backtest-line-chart"
                  viewBox="0 0 320 120"
                  role="img"
                  aria-label="回撤曲线"
                >
                  <line x1="16" y1="16" x2="304" y2="16" />
                  <line x1="16" y1="60" x2="304" y2="60" />
                  <line x1="16" y1="104" x2="304" y2="104" />
                  <polyline
                    data-testid="drawdown-chart-line"
                    class="backtest-line-chart__line backtest-line-chart__line--drawdown"
                    :points="selectedDrawdownChart.points"
                  />
                </svg>
                <footer>
                  <span>{{ selectedDrawdownChart.startLabel }}</span>
                  <span>{{ selectedDrawdownChart.endLabel }}</span>
                </footer>
                <small>
                  低 {{ selectedDrawdownChart.minLabel }} · 高 {{ selectedDrawdownChart.maxLabel }}
                </small>
              </article>
            </div>
            <section v-if="selectedTradeReviews.length" class="trade-review">
              <header>
                <strong>交易复盘</strong>
                <small>{{ selectedTradeReviews.length }} 个触发点</small>
              </header>
              <ol>
                <li
                  v-for="review in selectedTradeReviews"
                  :key="review.id"
                  :class="review.side === 'BUY' ? 'trade-review__item--buy' : 'trade-review__item--sell'"
                >
                  <div>
                    <span>{{ review.time }}</span>
                    <b>{{ review.quantityText }}</b>
                  </div>
                  <p>{{ review.reason }}</p>
                  <small>{{ review.priceText }}</small>
                </li>
              </ol>
            </section>
            <table class="space-table">
              <thead>
                <tr>
                  <th>时间</th>
                  <th>方向</th>
                  <th>价格</th>
                  <th>原因</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="trade in selectedBacktest.trades" :key="`${trade.time}-${trade.side}`">
                  <td>{{ trade.time }}</td>
                  <td>{{ trade.side }}</td>
                  <td>{{ trade.price }}</td>
                  <td>{{ trade.reason }}</td>
                </tr>
              </tbody>
            </table>
            <p class="space-muted">
              最新资金 {{ selectedBacktest.equityCurve[selectedBacktest.equityCurve.length - 1]?.equity }}
            </p>
          </template>
          <p v-else class="space-muted">选择一条回测记录</p>
        </aside>
      </div>

      <footer class="space-footer">
        <span>共 {{ backtestTotal }} 条回测</span>
        <div class="space-pagination">
          <button
            type="button"
            data-pagination="backtests-prev"
            :disabled="backtestPage <= 1"
            @click="changeBacktestPage(backtestPage - 1)"
          >
            上一页
          </button>
          <span>第 {{ backtestPage }} / {{ backtestTotalPages }} 页</span>
          <button
            type="button"
            data-pagination="backtests-next"
            :disabled="backtestPage >= backtestTotalPages"
            @click="changeBacktestPage(backtestPage + 1)"
          >
            下一页
          </button>
        </div>
      </footer>
    </section>
  </section>
</template>
