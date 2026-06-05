import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiClient } from '../src/api/http'
import { useStrategyWorkspaceStore } from '../src/stores/strategyWorkspace'
import PersonalSpaceView from '../src/views/PersonalSpaceView.vue'

const pushMock = vi.hoisted(() => vi.fn())

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: pushMock
  })
}))

vi.mock('../src/api/http', () => ({
  apiClient: {
    get: vi.fn(),
    delete: vi.fn()
  }
}))

const savedStrategy = {
  id: 7,
  name: '五分钟突破策略',
  description: '买入后退出',
  ownerId: 1,
  isPublic: false,
  createdAt: '2026-06-05T12:00:00',
  updatedAt: '2026-06-05T12:30:00',
  strategy: {
    version: 1,
    nodes: [
      {
        id: 'buy-1',
        type: 'buy',
        label: '买入',
        x: 72,
        y: 96,
        params: { sizePercent: '20', orderType: 'market' }
      }
    ],
    edges: [],
    viewport: { x: 0, y: 0, scale: 1 }
  },
  backtestConfig: {
    market: 'A_SHARE',
    symbol: '000001.SZ',
    timeframe: '5m',
    startDate: '2026-01-01',
    endDate: '2026-03-01',
    initialCash: 100000
  }
}

const savedBacktest = {
  id: 11,
  runId: 'engine-000001.SZ-5m',
  status: 'COMPLETED',
  market: 'A_SHARE',
  symbol: '000001.SZ',
  timeframe: '5m',
  startDate: '2026-01-01',
  endDate: '2026-03-01',
  totalReturnPercent: 7.35,
  maxDrawdownPercent: 2.1,
  winRatePercent: 66.7,
  endingEquity: 107350,
  tradeCount: 4,
  createdAt: '2026-06-06T10:00:00'
}

const backtestDetail = {
  ...savedBacktest,
  strategy: savedStrategy.strategy,
  config: savedStrategy.backtestConfig,
  summary: {
    totalReturnPercent: 7.35,
    maxDrawdownPercent: 2.1,
    winRatePercent: 66.7,
    endingEquity: 107350,
    tradeCount: 4
  },
  trades: [
    {
      time: '2026-01-01 09:35',
      side: 'BUY',
      price: 10.25,
      quantity: 1900,
      reason: '买入积木触发'
    },
    {
      time: '2026-01-01 10:00',
      side: 'SELL',
      price: 10.88,
      quantity: 1900,
      reason: '回测结束清仓'
    }
  ],
  equityCurve: [
    { time: '2026-01-01 09:35', equity: 100000 },
    { time: '2026-01-01 10:00', equity: 107350 }
  ]
}

function mockPersonalSpaceRequests() {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === '/strategies') {
      return Promise.resolve({
        data: {
          items: [savedStrategy],
          total: 1,
          page: 1,
          pageSize: 10
        }
      })
    }
    if (url === '/backtests') {
      return Promise.resolve({
        data: {
          items: [savedBacktest],
          total: 1,
          page: 1,
          pageSize: 10
        }
      })
    }
    if (url === '/backtests/11') {
      return Promise.resolve({ data: backtestDetail })
    }
    return Promise.reject(new Error(`Unhandled GET ${url}`))
  })
}

describe('personal space view', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('loads saved strategies and opens one in the builder workspace', async () => {
    mockPersonalSpaceRequests()
    const wrapper = mount(PersonalSpaceView)

    await flushPromises()

    expect(apiClient.get).toHaveBeenCalledWith('/strategies', {
      params: { keyword: '', page: 1, pageSize: 10 }
    })
    expect(apiClient.get).toHaveBeenCalledWith('/backtests', {
      params: { keyword: '', page: 1, pageSize: 10 }
    })
    expect(wrapper.text()).toContain('概览')
    expect(wrapper.text()).toContain('我的策略')
    expect(wrapper.text()).toContain('我的回测')
    expect(wrapper.text()).toContain('策略总数')
    expect(wrapper.text()).toContain('回测总数')
    expect(wrapper.text()).toContain('五分钟突破策略')
    expect(wrapper.text()).toContain('000001.SZ')

    await wrapper.find('.strategy-open-button').trigger('click')

    const workspaceStore = useStrategyWorkspaceStore()
    expect(workspaceStore.pendingStrategy?.id).toBe(7)
    expect(workspaceStore.pendingStrategy?.strategy.nodes[0].type).toBe('buy')
    expect(pushMock).toHaveBeenCalledWith('/')
  })

  it('deletes a saved strategy from the list', async () => {
    mockPersonalSpaceRequests()
    vi.mocked(apiClient.delete).mockResolvedValueOnce({ data: null })
    const wrapper = mount(PersonalSpaceView)

    await flushPromises()
    await wrapper.find('[data-space-tab="strategies"]').trigger('click')
    await wrapper.find('.strategy-delete-button').trigger('click')

    expect(apiClient.delete).toHaveBeenCalledWith('/strategies/7')
    expect(apiClient.get).toHaveBeenCalledWith('/strategies', {
      params: { keyword: '', page: 1, pageSize: 10 }
    })
  })

  it('shows saved backtests and opens a detail panel', async () => {
    mockPersonalSpaceRequests()
    const wrapper = mount(PersonalSpaceView)

    await flushPromises()
    await wrapper.find('[data-space-tab="backtests"]').trigger('click')

    expect(wrapper.text()).toContain('7.35%')
    expect(wrapper.text()).toContain('最大回撤 2.1%')
    expect(wrapper.text()).toContain('4 笔')

    await wrapper.find('.backtest-open-button').trigger('click')
    await flushPromises()

    expect(apiClient.get).toHaveBeenCalledWith('/backtests/11')
    expect(wrapper.text()).toContain('回测详情')
    expect(wrapper.text()).toContain('买入积木触发')
    expect(wrapper.text()).toContain('107350')
  })
})
