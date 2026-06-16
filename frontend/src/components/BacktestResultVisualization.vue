<script setup lang="ts">
import { computed } from 'vue'

type TradeSide = 'BUY' | 'SELL'

interface BacktestSummary {
  totalReturnPercent: number
  maxDrawdownPercent: number
  winRatePercent: number
  endingEquity: number
  tradeCount: number
}

interface BacktestTrade {
  time: string
  side: TradeSide
  price: number
  quantity: number
  reason: string
  grossAmount?: number
  costAmount?: number
  slippageAmount?: number
  netCashChange?: number
  costBreakdown?: Record<string, number>
}

interface BacktestEvent {
  time: string
  eventType: 'BLOCKED_ORDER'
  side: TradeSide
  price: number
  quantity: number
  reason: string
  rule: string
}

interface BacktestTimelineItem {
  id: string
  time: string
  eventType: 'TRADE_FILLED' | 'ORDER_BLOCKED' | 'COOLDOWN_STARTED' | 'POSITION_CLOSED'
  title: string
  description: string
  severity: 'info' | 'success' | 'warning' | 'danger'
  side?: TradeSide | null
  price?: number | null
  quantity?: number | null
  rule?: string | null
  nodeId?: string | null
  nodeType?: string | null
  nodeLabel?: string | null
  details: Record<string, string | number | boolean>
}

interface EquityPoint {
  time: string
  equity: number
}

interface BacktestVisualizationResult {
  summary: BacktestSummary
  trades: BacktestTrade[]
  events: BacktestEvent[]
  timeline?: BacktestTimelineItem[]
  equityCurve: EquityPoint[]
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
  side: TradeSide
  sideLabel: string
  testId: string
  label: string
}

interface TradeReviewItem {
  id: string
  time: string
  side: TradeSide
  sideLabel: string
  quantityText: string
  priceText: string
  reason: string
}

const props = withDefaults(
  defineProps<{
    result: BacktestVisualizationResult
    showMetrics?: boolean
  }>(),
  {
    showMetrics: false
  }
)

const chartWidth = 320
const chartHeight = 120
const chartPadding = 16

const equityChart = computed(() =>
  buildChartModel(
    props.result.equityCurve.map((point) => ({ time: point.time, value: point.equity })),
    {
      highValueAtTop: true,
      formatLabel: (value) => formatAmount(value)
    }
  )
)

const drawdownChart = computed(() => {
  let peak = 0
  const drawdownPoints = props.result.equityCurve.map<ChartDataPoint>((point) => {
    peak = Math.max(peak, point.equity)
    return {
      time: point.time,
      value: peak > 0 ? ((peak - point.equity) / peak) * 100 : 0
    }
  })

  return buildChartModel(drawdownPoints, {
    highValueAtTop: false,
    minValue: 0,
    formatLabel: (value) => formatPercent(value)
  })
})

const equityTradeMarkers = computed<TradeMarker[]>(() => {
  if (!equityChart.value) {
    return []
  }

  const coordinateByTime = new Map(
    equityChart.value.coordinates.map((coordinate) => [coordinate.time, coordinate])
  )

  return props.result.trades.flatMap((trade, index) => {
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

const tradeReviews = computed<TradeReviewItem[]>(() =>
  props.result.trades.map((trade, index) => {
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
    return {
      ...point,
      x,
      y: chartPadding + yRatio * (chartHeight - chartPadding * 2)
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

function formatSignedAmount(value: number | undefined) {
  const numericValue = Number(value ?? 0)
  const sign = numericValue > 0 ? '+' : ''
  return `${sign}${formatAmount(numericValue)}`
}

function formatTradeSide(side: TradeSide) {
  return side === 'BUY' ? '买入' : '卖出'
}

function timelineMeta(item: BacktestTimelineItem) {
  const parts: string[] = []
  if (item.nodeLabel) {
    parts.push(`积木 ${item.nodeLabel}`)
  }
  if (item.side) {
    parts.push(formatTradeSide(item.side))
  }
  if (typeof item.quantity === 'number') {
    parts.push(`${item.quantity} 股`)
  }
  if (typeof item.price === 'number') {
    parts.push(formatAmount(item.price))
  }
  if (item.rule) {
    parts.push(`规则 ${item.rule}`)
  }
  if (typeof item.details.durationBars === 'number') {
    parts.push(`冷却 ${item.details.durationBars} 根K线`)
  }
  return parts.join(' · ') || item.time
}
</script>

<template>
  <div class="backtest-visualization">
    <div v-if="showMetrics" class="backtest-metrics">
      <span>
        <small>总收益率</small>
        <b>{{ formatPercent(result.summary.totalReturnPercent) }}</b>
      </span>
      <span>
        <small>最大回撤</small>
        <b>{{ formatPercent(result.summary.maxDrawdownPercent) }}</b>
      </span>
      <span>
        <small>胜率</small>
        <b>{{ formatPercent(result.summary.winRatePercent) }}</b>
      </span>
      <span>
        <small>期末资产</small>
        <b>{{ formatAmount(result.summary.endingEquity) }}</b>
      </span>
    </div>

    <div v-if="equityChart || drawdownChart" class="backtest-chart-grid">
      <article v-if="equityChart" class="backtest-chart-card">
        <header>
          <span>权益曲线</span>
          <small>{{ equityChart.latestLabel }}</small>
        </header>
        <svg class="backtest-line-chart" viewBox="0 0 320 120" role="img" aria-label="权益曲线">
          <line x1="16" y1="16" x2="304" y2="16" />
          <line x1="16" y1="60" x2="304" y2="60" />
          <line x1="16" y1="104" x2="304" y2="104" />
          <polyline
            data-testid="equity-chart-line"
            class="backtest-line-chart__line backtest-line-chart__line--equity"
            :points="equityChart.points"
          />
          <g
            v-for="marker in equityTradeMarkers"
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
          <span>{{ equityChart.startLabel }}</span>
          <span>{{ equityChart.endLabel }}</span>
        </footer>
        <small>低 {{ equityChart.minLabel }} · 高 {{ equityChart.maxLabel }}</small>
      </article>

      <article v-if="drawdownChart" class="backtest-chart-card">
        <header>
          <span>回撤曲线</span>
          <small>{{ drawdownChart.latestLabel }}</small>
        </header>
        <svg class="backtest-line-chart" viewBox="0 0 320 120" role="img" aria-label="回撤曲线">
          <line x1="16" y1="16" x2="304" y2="16" />
          <line x1="16" y1="60" x2="304" y2="60" />
          <line x1="16" y1="104" x2="304" y2="104" />
          <polyline
            data-testid="drawdown-chart-line"
            class="backtest-line-chart__line backtest-line-chart__line--drawdown"
            :points="drawdownChart.points"
          />
        </svg>
        <footer>
          <span>{{ drawdownChart.startLabel }}</span>
          <span>{{ drawdownChart.endLabel }}</span>
        </footer>
        <small>低 {{ drawdownChart.minLabel }} · 高 {{ drawdownChart.maxLabel }}</small>
      </article>
    </div>

    <section v-if="tradeReviews.length" class="trade-review">
      <header>
        <strong>交易复盘</strong>
        <small>{{ tradeReviews.length }} 个触发点</small>
      </header>
      <ol>
        <li
          v-for="review in tradeReviews"
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

    <section v-if="result.timeline?.length" class="backtest-timeline">
      <header>
        <strong>策略执行时间线</strong>
        <small>{{ (result.timeline ?? []).length }} 条记录</small>
      </header>
      <ol>
        <li
          v-for="item in result.timeline ?? []"
          :key="item.id"
          :class="`timeline-item--${item.severity}`"
        >
          <div>
            <b>{{ item.title }}</b>
            <span>{{ item.time }}</span>
          </div>
          <p>{{ item.description }}</p>
          <small>{{ timelineMeta(item) }}</small>
        </li>
      </ol>
    </section>

    <section v-if="result.events.length" class="backtest-events">
      <header>
        <strong>规则提示</strong>
        <small>{{ result.events.length }} 条被拦截信号</small>
      </header>
      <ul>
        <li
          v-for="(event, index) in result.events"
          :key="`${event.time}-${event.side}-${event.rule}-${index}`"
        >
          <div>
            <b>{{ event.time }} · {{ event.side === 'BUY' ? '买入' : '卖出' }}信号被拦截</b>
            <span>{{ event.rule }}</span>
          </div>
          <p>{{ event.reason }}</p>
          <small>{{ event.quantity }} 股 · {{ formatAmount(event.price) }}</small>
        </li>
      </ul>
    </section>

    <table v-if="result.trades.length" class="backtest-trades">
      <thead>
        <tr>
          <th>时间</th>
          <th>方向</th>
          <th>价格</th>
          <th>数量</th>
          <th>成本</th>
          <th>净现金变化</th>
          <th>原因</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="trade in result.trades" :key="`${trade.time}-${trade.side}-${trade.reason}`">
          <td>{{ trade.time }}</td>
          <td>{{ trade.side }}</td>
          <td>{{ formatAmount(trade.price) }}</td>
          <td>{{ trade.quantity }}</td>
          <td>{{ formatAmount(trade.costAmount) }}</td>
          <td>{{ formatSignedAmount(trade.netCashChange) }}</td>
          <td>{{ trade.reason }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
