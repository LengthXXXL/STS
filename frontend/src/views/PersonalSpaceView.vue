<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { apiClient } from '../api/http'
import {
  useStrategyWorkspaceStore,
  type SavedStrategy
} from '../stores/strategyWorkspace'

type SpaceTab = 'overview' | 'strategies' | 'backtests'

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
  createdAt: string
}

interface BacktestListResponse {
  items: BacktestListItem[]
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

interface BacktestDetail extends BacktestListItem {
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
const workspaceStore = useStrategyWorkspaceStore()
const activeTab = ref<SpaceTab>('overview')
const strategies = ref<SavedStrategy[]>([])
const backtests = ref<BacktestListItem[]>([])
const selectedBacktest = ref<BacktestDetail | null>(null)
const strategyKeyword = ref('')
const backtestKeyword = ref('')
const strategyPage = ref(1)
const backtestPage = ref(1)
const pageSize = 10
const strategyTotal = ref(0)
const backtestTotal = ref(0)
const strategyLoading = ref(false)
const backtestLoading = ref(false)
const backtestDetailLoading = ref(false)
const strategyError = ref('')
const backtestError = ref('')

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
const latestBacktest = computed(() => backtests.value[0] ?? null)

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

async function openBacktest(backtest: BacktestListItem) {
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

function formatDate(value: string | undefined) {
  return value ? value.slice(0, 10) : '-'
}

onMounted(() => {
  void loadStrategies()
  void loadBacktests()
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
      </footer>
    </section>

    <section v-else class="space-section space-backtests">
      <p v-if="backtestError" class="form-error">{{ backtestError }}</p>
      <p v-else-if="backtestLoading" class="space-muted">正在加载回测</p>
      <p v-else-if="backtests.length === 0" class="space-muted">暂无回测记录</p>

      <div v-else class="backtest-layout">
        <div class="backtest-list">
          <article v-for="backtest in backtests" :key="backtest.id" class="backtest-item">
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
              </small>
            </div>
            <button class="backtest-open-button" type="button" @click="openBacktest(backtest)">
              查看
            </button>
          </article>
        </div>

        <aside class="space-detail-panel">
          <p v-if="backtestDetailLoading" class="space-muted">正在加载详情</p>
          <template v-else-if="selectedBacktest">
            <strong>回测详情</strong>
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
      </footer>
    </section>
  </section>
</template>
