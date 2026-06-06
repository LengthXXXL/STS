import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiClient } from '../src/api/http'
import { useAuthStore } from '../src/stores/auth'
import { useStrategyWorkspaceStore } from '../src/stores/strategyWorkspace'
import PersonalSpaceView from '../src/views/PersonalSpaceView.vue'

const pushMock = vi.hoisted(() => vi.fn())
const routeMock = vi.hoisted(() => ({
  query: {} as Record<string, string>
}))

vi.mock('vue-router', () => ({
  useRoute: () => routeMock,
  useRouter: () => ({
    push: pushMock
  })
}))

vi.mock('../src/api/http', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
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
      },
      {
        id: 'stop-loss-1',
        type: 'stop-loss',
        label: '止损',
        x: 220,
        y: 96,
        params: { lossPercent: '3', sellPercent: '100' }
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
  simulationAccountId: 3,
  simulationAccountName: 'A股日内账户',
  createdAt: '2026-06-06T10:00:00'
}

const savedAccount = {
  id: 3,
  ownerId: 1,
  name: 'A股日内账户',
  description: '专门用于五分钟策略测试',
  market: 'A_SHARE',
  initialCash: 100000,
  createdAt: '2026-06-06T09:00:00',
  updatedAt: '2026-06-06T09:00:00'
}

const savedCustomBlock = {
  id: 21,
  ownerId: 1,
  name: '突破止盈模板',
  description: '买入后按收益目标退出',
  category: '风控',
  tags: ['止盈', '模板'],
  template: savedStrategy.strategy,
  reviewStatus: 'private',
  createdAt: '2026-06-06T11:00:00',
  updatedAt: '2026-06-06T11:30:00'
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
    if (url === '/simulation-accounts') {
      return Promise.resolve({
        data: {
          items: [savedAccount],
          total: 1,
          page: 1,
          pageSize: 10
        }
      })
    }
    if (url === '/custom-blocks') {
      return Promise.resolve({
        data: {
          items: [savedCustomBlock],
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

function mockPersonalSpaceRequestsWithDelayedBacktestDetail() {
  let resolveDetail: (value: { data: typeof backtestDetail }) => void = () => {}

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
    if (url === '/simulation-accounts') {
      return Promise.resolve({
        data: {
          items: [savedAccount],
          total: 1,
          page: 1,
          pageSize: 10
        }
      })
    }
    if (url === '/custom-blocks') {
      return Promise.resolve({
        data: {
          items: [savedCustomBlock],
          total: 1,
          page: 1,
          pageSize: 10
        }
      })
    }
    if (url === '/backtests/11') {
      return new Promise((resolve) => {
        resolveDetail = resolve
      })
    }
    return Promise.reject(new Error(`Unhandled GET ${url}`))
  })

  return {
    resolveDetail: () => resolveDetail({ data: backtestDetail })
  }
}

describe('personal space view', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    routeMock.query = {}
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
    expect(apiClient.get).toHaveBeenCalledWith('/simulation-accounts', {
      params: { keyword: '', page: 1, pageSize: 10 }
    })
    expect(apiClient.get).toHaveBeenCalledWith('/custom-blocks', {
      params: { keyword: '', page: 1, pageSize: 10 }
    })
    expect(wrapper.text()).toContain('概览')
    expect(wrapper.text()).toContain('我的策略')
    expect(wrapper.text()).toContain('我的积木')
    expect(wrapper.text()).toContain('模拟账户')
    expect(wrapper.text()).toContain('我的回测')
    expect(wrapper.text()).toContain('策略总数')
    expect(wrapper.text()).toContain('账户总数')
    expect(wrapper.text()).toContain('回测总数')
    expect(wrapper.text()).toContain('五分钟突破策略')
    expect(wrapper.text()).toContain('突破止盈模板')
    expect(wrapper.text()).toContain('A股日内账户')
    expect(wrapper.text()).toContain('000001.SZ')

    await wrapper.find('.strategy-open-button').trigger('click')

    const workspaceStore = useStrategyWorkspaceStore()
    expect(workspaceStore.pendingStrategy?.id).toBe(7)
    expect(workspaceStore.pendingStrategy?.strategy.nodes[0].type).toBe('buy')
    expect(pushMock).toHaveBeenCalledWith('/')
  })

  it('reloads personal space data after a user logs in on the page', async () => {
    vi.mocked(apiClient.get).mockRejectedValue(new Error('Not authenticated'))
    const wrapper = mount(PersonalSpaceView)

    await flushPromises()
    expect(apiClient.get).toHaveBeenCalledTimes(4)

    mockPersonalSpaceRequests()
    const authStore = useAuthStore()
    authStore.setSession({
      token: 'token-123',
      user: {
        id: 1,
        username: 'alice',
        email: 'alice@example.com',
        roles: ['user']
      }
    })
    await nextTick()
    await flushPromises()

    expect(apiClient.get).toHaveBeenCalledTimes(8)
    expect(wrapper.text()).toContain('五分钟突破策略')
    expect(wrapper.text()).toContain('A股日内账户')
    expect(wrapper.text()).toContain('000001.SZ')
  })

  it('opens the backtest tab from the route query', async () => {
    routeMock.query = { tab: 'backtests' }
    mockPersonalSpaceRequests()
    const wrapper = mount(PersonalSpaceView)

    await flushPromises()

    expect(wrapper.find('[data-space-tab="backtests"]').classes()).toContain('is-active')
    expect(wrapper.text()).toContain('7.35%')
    expect(wrapper.text()).toContain('使用账户 A股日内账户')
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

  it('shows and deletes custom block templates from the list', async () => {
    mockPersonalSpaceRequests()
    vi.mocked(apiClient.delete).mockResolvedValueOnce({ data: null })
    const wrapper = mount(PersonalSpaceView)

    await flushPromises()
    await wrapper.find('[data-space-tab="custom-blocks"]').trigger('click')

    expect(wrapper.text()).toContain('突破止盈模板')
    expect(wrapper.text()).toContain('风控')
    expect(wrapper.text()).toContain('止盈')
    expect(wrapper.text()).toContain('私有模板')
    expect(wrapper.text()).toContain('2 个积木')

    await wrapper.find('.custom-block-delete-button').trigger('click')

    expect(apiClient.delete).toHaveBeenCalledWith('/custom-blocks/21')
    expect(apiClient.get).toHaveBeenCalledWith('/custom-blocks', {
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
    expect(wrapper.text()).toContain('使用账户 A股日内账户')

    await wrapper.find('.backtest-open-button').trigger('click')
    await flushPromises()

    expect(apiClient.get).toHaveBeenCalledWith('/backtests/11')
    expect(wrapper.find('.backtest-item.is-selected').exists()).toBe(true)
    expect(wrapper.find('.backtest-open-button').text()).toBe('收起')
    expect(wrapper.find('.backtest-close-button').exists()).toBe(true)
    expect(wrapper.text()).toContain('回测详情')
    expect(wrapper.text()).toContain('买入积木触发')
    expect(wrapper.text()).toContain('账户 A股日内账户')
    expect(wrapper.text()).toContain('107350')
    expect(wrapper.text()).toContain('权益曲线')
    expect(wrapper.text()).toContain('回撤曲线')
    expect(wrapper.find('[data-testid="equity-chart-line"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="drawdown-chart-line"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="trade-marker-buy"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="trade-marker-sell"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('交易复盘')
    expect(wrapper.text()).toContain('买入 1900 股')
    expect(wrapper.text()).toContain('卖出 1900 股')
    expect(wrapper.text()).toContain('回测快照')
    expect(wrapper.text()).toContain('市场A股')
    expect(wrapper.text()).toContain('股票000001.SZ')
    expect(wrapper.text()).toContain('周期5分钟')
    expect(wrapper.text()).toContain('区间2026-01-01 至 2026-03-01')
    expect(wrapper.text()).toContain('初始资金100,000')
    expect(wrapper.text()).toContain('策略积木')
    expect(wrapper.text()).toContain('2 个')
    expect(wrapper.text()).toContain('买入 x1')
    expect(wrapper.text()).toContain('止损 x1')
  })

  it('opens a backtest strategy snapshot in the builder workspace', async () => {
    mockPersonalSpaceRequests()
    const wrapper = mount(PersonalSpaceView)

    await flushPromises()
    await wrapper.find('[data-space-tab="backtests"]').trigger('click')
    await wrapper.find('.backtest-open-button').trigger('click')
    await flushPromises()

    expect(wrapper.find('.backtest-replay-button').exists()).toBe(true)

    await wrapper.find('.backtest-replay-button').trigger('click')

    const workspaceStore = useStrategyWorkspaceStore()
    expect(workspaceStore.pendingWorkspaceDraft?.source).toBe('backtest-snapshot')
    expect(workspaceStore.pendingWorkspaceDraft?.name).toContain('回测复盘')
    expect(workspaceStore.pendingWorkspaceDraft?.strategy.nodes[0].type).toBe('buy')
    expect(workspaceStore.pendingWorkspaceDraft?.backtestConfig).toMatchObject({
      symbol: '000001.SZ',
      timeframe: '5m',
      simulationAccountId: 3
    })
    expect(pushMock).toHaveBeenCalledWith('/')
  })

  it('closes an opened backtest detail from the panel or selected list item', async () => {
    mockPersonalSpaceRequests()
    const wrapper = mount(PersonalSpaceView)

    await flushPromises()
    await wrapper.find('[data-space-tab="backtests"]').trigger('click')
    await wrapper.find('.backtest-open-button').trigger('click')
    await flushPromises()

    await wrapper.find('.backtest-close-button').trigger('click')

    expect(wrapper.text()).toContain('选择一条回测记录')
    expect(wrapper.find('.backtest-item.is-selected').exists()).toBe(false)
    expect(wrapper.find('.backtest-open-button').text()).toBe('查看')

    await wrapper.find('.backtest-open-button').trigger('click')
    await flushPromises()
    await wrapper.find('.backtest-open-button').trigger('click')

    expect(wrapper.text()).toContain('选择一条回测记录')
    expect(wrapper.find('.backtest-item.is-selected').exists()).toBe(false)
    expect(wrapper.find('.backtest-open-button').text()).toBe('查看')
  })

  it('keeps the detail panel stable while loading a backtest detail', async () => {
    const detailRequest = mockPersonalSpaceRequestsWithDelayedBacktestDetail()
    const wrapper = mount(PersonalSpaceView)

    await flushPromises()
    await wrapper.find('[data-space-tab="backtests"]').trigger('click')
    await wrapper.find('.backtest-open-button').trigger('click')
    await nextTick()

    expect(wrapper.text()).toContain('选择一条回测记录')
    expect(wrapper.text()).not.toContain('正在加载详情')

    detailRequest.resolveDetail()
    await flushPromises()

    expect(wrapper.text()).toContain('回测详情')
    expect(wrapper.text()).toContain('回测快照')
  })

  it('creates, edits and deletes a simulation account', async () => {
    mockPersonalSpaceRequests()
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: savedAccount })
    vi.mocked(apiClient.put).mockResolvedValueOnce({
      data: { ...savedAccount, name: '美股一分钟账户', market: 'US_STOCK', initialCash: 50000 }
    })
    vi.mocked(apiClient.delete).mockResolvedValueOnce({ data: null })
    const wrapper = mount(PersonalSpaceView)

    await flushPromises()
    await wrapper.find('[data-space-tab="accounts"]').trigger('click')

    expect(wrapper.text()).toContain('A股日内账户')
    expect(wrapper.text()).toContain('100000')

    await wrapper.find('.account-name-input').setValue('美股一分钟账户')
    await wrapper.find('.account-market-select').setValue('US_STOCK')
    await wrapper.find('.account-cash-input').setValue('50000')
    await wrapper.find('.account-description-input').setValue('一分钟策略测试')
    await wrapper.find('.account-submit-button').trigger('click')

    expect(apiClient.post).toHaveBeenCalledWith('/simulation-accounts', {
      name: '美股一分钟账户',
      description: '一分钟策略测试',
      market: 'US_STOCK',
      initialCash: 50000
    })
    await flushPromises()

    await wrapper.find('.account-edit-button').trigger('click')
    await wrapper.find('.account-name-input').setValue('美股一分钟账户')
    await wrapper.find('.account-submit-button').trigger('click')

    expect(apiClient.put).toHaveBeenCalledWith('/simulation-accounts/3', {
      name: '美股一分钟账户',
      description: '专门用于五分钟策略测试',
      market: 'A_SHARE',
      initialCash: 100000
    })

    await wrapper.find('.account-delete-button').trigger('click')
    expect(apiClient.delete).toHaveBeenCalledWith('/simulation-accounts/3')
  })

  it('changes pages for strategy, account and backtest lists', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string, config?: { params?: { page?: number } }) => {
      const page = config?.params?.page ?? 1
      if (url === '/strategies') {
        return Promise.resolve({
          data: { items: [savedStrategy], total: 11, page, pageSize: 10 }
        })
      }
      if (url === '/simulation-accounts') {
        return Promise.resolve({
          data: { items: [savedAccount], total: 11, page, pageSize: 10 }
        })
      }
      if (url === '/backtests') {
        return Promise.resolve({
          data: { items: [savedBacktest], total: 11, page, pageSize: 10 }
        })
      }
      return Promise.reject(new Error(`Unhandled GET ${url}`))
    })
    const wrapper = mount(PersonalSpaceView)

    await flushPromises()
    await wrapper.find('[data-space-tab="strategies"]').trigger('click')
    await wrapper.find('[data-pagination="strategies-next"]').trigger('click')
    expect(apiClient.get).toHaveBeenCalledWith('/strategies', {
      params: { keyword: '', page: 2, pageSize: 10 }
    })

    await wrapper.find('[data-space-tab="accounts"]').trigger('click')
    await wrapper.find('[data-pagination="accounts-next"]').trigger('click')
    expect(apiClient.get).toHaveBeenCalledWith('/simulation-accounts', {
      params: { keyword: '', page: 2, pageSize: 10 }
    })

    await wrapper.find('[data-space-tab="backtests"]').trigger('click')
    await wrapper.find('[data-pagination="backtests-next"]').trigger('click')
    expect(apiClient.get).toHaveBeenCalledWith('/backtests', {
      params: { keyword: '', page: 2, pageSize: 10 }
    })
  })
})
