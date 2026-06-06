import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiClient } from '../src/api/http'
import { useAuthStore } from '../src/stores/auth'
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
    if (url === '/backtests/11') {
      return Promise.resolve({ data: backtestDetail })
    }
    return Promise.reject(new Error(`Unhandled GET ${url}`))
  })
}

describe('personal space view', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
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
    expect(wrapper.text()).toContain('概览')
    expect(wrapper.text()).toContain('我的策略')
    expect(wrapper.text()).toContain('模拟账户')
    expect(wrapper.text()).toContain('我的回测')
    expect(wrapper.text()).toContain('策略总数')
    expect(wrapper.text()).toContain('账户总数')
    expect(wrapper.text()).toContain('回测总数')
    expect(wrapper.text()).toContain('五分钟突破策略')
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
    expect(apiClient.get).toHaveBeenCalledTimes(3)

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

    expect(apiClient.get).toHaveBeenCalledTimes(6)
    expect(wrapper.text()).toContain('五分钟突破策略')
    expect(wrapper.text()).toContain('A股日内账户')
    expect(wrapper.text()).toContain('000001.SZ')
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
    expect(wrapper.text()).toContain('使用账户 A股日内账户')

    await wrapper.find('.backtest-open-button').trigger('click')
    await flushPromises()

    expect(apiClient.get).toHaveBeenCalledWith('/backtests/11')
    expect(wrapper.text()).toContain('回测详情')
    expect(wrapper.text()).toContain('买入积木触发')
    expect(wrapper.text()).toContain('账户 A股日内账户')
    expect(wrapper.text()).toContain('107350')
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
