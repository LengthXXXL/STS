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

const marketRules = [
  {
    market: 'A_SHARE',
    marketLabel: 'A股',
    currency: 'CNY',
    timezone: 'Asia/Shanghai',
    settlementCycle: 'T+1',
    buyLotSize: 100,
    sellLotSize: 1,
    minOrderShares: 100,
    supportsIntradayRoundTrip: false,
    priceLimitPercent: 10,
    sessions: [
      { label: '上午连续竞价', start: '09:30', end: '11:30' },
      { label: '下午连续竞价', start: '13:00', end: '15:00' }
    ],
    notes: [
      '买入委托数量按 100 股整数倍处理。',
      '普通 A 股主板按 T+1 可卖规则处理，买入当日不可卖出。',
      '普通 A 股主板默认按前收盘价上下 10% 涨跌停限制处理。'
    ]
  },
  {
    market: 'US_STOCK',
    marketLabel: '美股',
    currency: 'USD',
    timezone: 'America/New_York',
    settlementCycle: 'T+1',
    buyLotSize: 1,
    sellLotSize: 1,
    minOrderShares: 1,
    supportsIntradayRoundTrip: true,
    priceLimitPercent: null,
    sessions: [{ label: '常规交易时段', start: '09:30', end: '16:00' }],
    notes: ['常规股票交易按 1 股为最小整数股单位处理。', 'V1 只模拟常规交易时段，不模拟盘前盘后交易。']
  }
]

const savedCustomBlock = {
  id: 21,
  ownerId: 1,
  name: '突破止盈模板',
  description: '买入后按收益目标退出',
  category: '风控',
  tags: ['止盈', '模板'],
  template: {
    ...savedStrategy.strategy,
    edges: [{ id: 'custom-edge-1', from: 'buy-1', to: 'stop-loss-1' }]
  },
  reviewStatus: 'private',
  createdAt: '2026-06-06T11:00:00',
  updatedAt: '2026-06-06T11:30:00'
}

const savedForumPost = {
  id: 31,
  authorId: 1,
  authorName: 'alice',
  title: '待审核止盈复盘',
  content: '这是一条等待管理员审核的论坛帖子。',
  topic: '策略复盘',
  sharedBlockId: null,
  reviewStatus: 'pending_review',
  reviewReason: null,
  commentCount: 0,
  createdAt: '2026-06-07T09:00:00',
  updatedAt: '2026-06-07T09:30:00'
}

const rejectedForumPost = {
  ...savedForumPost,
  id: 32,
  title: '未通过论坛帖子',
  content: '这是一条没有通过审核的论坛帖子。',
  reviewStatus: 'rejected',
  reviewReason: '帖子缺少可复现的策略细节。'
}

const savedForumComment = {
  id: 41,
  postId: 12,
  postTitle: '公开止盈讨论帖',
  authorId: 1,
  authorName: 'alice',
  content: '这是一条被驳回的评论。',
  reviewStatus: 'rejected',
  reviewReason: '评论不够具体，无法帮助其他用户。',
  createdAt: '2026-06-07T10:00:00',
  updatedAt: '2026-06-07T10:30:00'
}

const savedFile = {
  id: 51,
  ownerId: 1,
  originalName: '策略说明.json',
  contentType: 'application/json',
  size: 2048,
  businessType: 'strategy',
  businessId: null,
  visibility: 'private',
  createdAt: '2026-06-08T09:00:00',
  downloadUrl: '/api/files/51/download'
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
  events: [
    {
      time: '2026-01-01 09:40',
      eventType: 'BLOCKED_ORDER',
      side: 'SELL',
      price: 10.6,
      quantity: 1900,
      reason: 'A股 T+1 规则限制，当日买入持仓不可卖出',
      rule: 'T+1'
    }
  ],
  timeline: [
    {
      id: 'trade-filled-0',
      time: '2026-01-01 09:35',
      eventType: 'TRADE_FILLED',
      title: '买入成交',
      description: '买入积木触发',
      severity: 'success',
      side: 'BUY',
      price: 10.25,
      quantity: 1900,
      rule: null,
      nodeId: 'buy-1',
      nodeType: 'buy',
      nodeLabel: '买入',
      details: {}
    },
    {
      id: 'order-blocked-1',
      time: '2026-01-01 09:40',
      eventType: 'ORDER_BLOCKED',
      title: '卖出信号被拦截',
      description: 'A股 T+1 规则限制，当日买入持仓不可卖出',
      severity: 'warning',
      side: 'SELL',
      price: 10.6,
      quantity: 1900,
      rule: 'T+1',
      nodeId: 'take-profit-1',
      nodeType: 'take-profit',
      nodeLabel: '止盈',
      details: {}
    }
  ],
  equityCurve: [
    { time: '2026-01-01 09:35', equity: 100000 },
    { time: '2026-01-01 10:00', equity: 107350 }
  ]
}

function mockPersonalSpaceRequests(
  options: {
    customBlocks?: Array<typeof savedCustomBlock>
    files?: Array<typeof savedFile>
  } = {}
) {
  const customBlockItems = options.customBlocks ?? [savedCustomBlock]
  const fileItems = options.files ?? [savedFile]

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
    if (url === '/market-rules') {
      return Promise.resolve({ data: { items: marketRules } })
    }
    if (url === '/custom-blocks') {
      return Promise.resolve({
        data: {
          items: customBlockItems,
          total: customBlockItems.length,
          page: 1,
          pageSize: 10
        }
      })
    }
    if (url === '/files') {
      return Promise.resolve({
        data: {
          items: fileItems,
          total: fileItems.length,
          page: 1,
          pageSize: 10
        }
      })
    }
    if (url === '/forum/my-posts') {
      return Promise.resolve({
        data: {
          items: [savedForumPost, rejectedForumPost],
          total: 2,
          page: 1,
          pageSize: 10
        }
      })
    }
    if (url === '/forum/my-comments') {
      return Promise.resolve({
        data: {
          items: [savedForumComment],
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
    if (url === '/market-rules') {
      return Promise.resolve({ data: { items: marketRules } })
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
    if (url === '/files') {
      return Promise.resolve({
        data: {
          items: [savedFile],
          total: 1,
          page: 1,
          pageSize: 10
        }
      })
    }
    if (url === '/forum/my-posts') {
      return Promise.resolve({
        data: { items: [savedForumPost, rejectedForumPost], total: 2, page: 1, pageSize: 10 }
      })
    }
    if (url === '/forum/my-comments') {
      return Promise.resolve({
        data: { items: [savedForumComment], total: 1, page: 1, pageSize: 10 }
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
    expect(apiClient.get).toHaveBeenCalledWith('/files', {
      params: { keyword: '', page: 1, pageSize: 10 }
    })
    expect(apiClient.get).toHaveBeenCalledWith('/forum/my-posts', {
      params: { page: 1, pageSize: 10 }
    })
    expect(apiClient.get).toHaveBeenCalledWith('/forum/my-comments', {
      params: { page: 1, pageSize: 10 }
    })
    expect(wrapper.text()).toContain('概览')
    expect(wrapper.text()).toContain('我的策略')
    expect(wrapper.text()).toContain('我的积木')
    expect(wrapper.text()).toContain('模拟账户')
    expect(wrapper.text()).toContain('我的回测')
    expect(wrapper.text()).toContain('文件管理')
    expect(wrapper.text()).toContain('我的论坛')
    expect(wrapper.text()).toContain('策略总数')
    expect(wrapper.text()).toContain('账户总数')
    expect(wrapper.text()).toContain('回测总数')
    expect(wrapper.text()).toContain('论坛内容')
    expect(wrapper.text()).toContain('文件总数')
    expect(wrapper.text()).toContain('五分钟突破策略')
    expect(wrapper.text()).toContain('突破止盈模板')
    expect(wrapper.text()).toContain('A股日内账户')
    expect(wrapper.text()).toContain('000001.SZ')
    expect(wrapper.text()).toContain('策略说明.json')

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
    expect(apiClient.get).toHaveBeenCalledTimes(8)

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

    expect(apiClient.get).toHaveBeenCalledTimes(16)
    expect(wrapper.text()).toContain('五分钟突破策略')
    expect(wrapper.text()).toContain('A股日内账户')
    expect(wrapper.text()).toContain('000001.SZ')
  })

  it('uploads, searches and deletes personal files', async () => {
    mockPersonalSpaceRequests()
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { ...savedFile, id: 52, originalName: '新策略说明.json' }
    })
    vi.mocked(apiClient.delete).mockResolvedValueOnce({ data: null })
    const wrapper = mount(PersonalSpaceView)

    await flushPromises()
    await wrapper.find('[data-space-tab="files"]').trigger('click')

    expect(wrapper.text()).toContain('策略说明.json')
    expect(wrapper.text()).toContain('策略附件')
    expect(wrapper.text()).toContain('2 KB')

    const file = new File(['{}'], '新策略说明.json', { type: 'application/json' })
    const input = wrapper.find('.file-upload-input')
    Object.defineProperty(input.element, 'files', {
      value: [file],
      configurable: true
    })
    await input.trigger('change')
    await wrapper.find('.file-upload-button').trigger('click')
    await flushPromises()

    expect(apiClient.post).toHaveBeenCalledWith('/files/upload', expect.any(FormData))
    expect(wrapper.text()).toContain('已上传文件：新策略说明.json')

    await wrapper.find('.space-search input').setValue('策略')
    await wrapper.find('.space-search').trigger('submit')
    await flushPromises()

    expect(apiClient.get).toHaveBeenCalledWith('/files', {
      params: { keyword: '策略', page: 1, pageSize: 10 }
    })

    await wrapper.find('.file-delete-button').trigger('click')
    await flushPromises()

    expect(apiClient.delete).toHaveBeenCalledWith('/files/51')
    expect(wrapper.text()).toContain('已删除文件：策略说明.json')
  })

  it('shows own forum posts and comments with review status', async () => {
    mockPersonalSpaceRequests()
    const wrapper = mount(PersonalSpaceView)

    await flushPromises()
    await wrapper.find('[data-space-tab="forum"]').trigger('click')

    expect(wrapper.text()).toContain('待审核止盈复盘')
    expect(wrapper.text()).toContain('审核中')
    expect(wrapper.text()).toContain('这是一条等待管理员审核的论坛帖子。')
    expect(wrapper.text()).toContain('未通过论坛帖子')
    expect(wrapper.text()).toContain('未通过原因：帖子缺少可复现的策略细节。')

    await wrapper.find('.space-forum-comments-tab').trigger('click')

    expect(wrapper.text()).toContain('公开止盈讨论帖')
    expect(wrapper.text()).toContain('这是一条被驳回的评论。')
    expect(wrapper.text()).toContain('未通过审核')
    expect(wrapper.text()).toContain('未通过原因：评论不够具体，无法帮助其他用户。')
    expect(wrapper.text()).toContain('关联帖子：公开止盈讨论帖')
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

  it('opens a backtest detail from the route query', async () => {
    routeMock.query = { tab: 'backtests', backtestId: '11' }
    mockPersonalSpaceRequests()
    const wrapper = mount(PersonalSpaceView)

    await flushPromises()

    expect(wrapper.find('[data-space-tab="backtests"]').classes()).toContain('is-active')
    expect(apiClient.get).toHaveBeenCalledWith('/backtests/11')
    expect(wrapper.find('.backtest-item.is-selected').exists()).toBe(true)
    expect(wrapper.text()).toContain('回测详情')
    expect(wrapper.text()).toContain('买入积木触发')
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

  it('renames a saved strategy without changing its content', async () => {
    mockPersonalSpaceRequests()
    vi.mocked(apiClient.put).mockResolvedValueOnce({
      data: { ...savedStrategy, name: '五分钟突破策略新版' }
    })
    const wrapper = mount(PersonalSpaceView)

    await flushPromises()
    await wrapper.find('[data-space-tab="strategies"]').trigger('click')
    await wrapper.find('.strategy-rename-button').trigger('click')

    expect((wrapper.find('.strategy-name-input').element as HTMLInputElement).value).toBe(
      '五分钟突破策略'
    )

    await wrapper.find('.strategy-name-input').setValue('五分钟突破策略新版')
    await wrapper.find('.strategy-save-name-button').trigger('click')
    await flushPromises()

    expect(apiClient.put).toHaveBeenCalledWith('/strategies/7', {
      name: '五分钟突破策略新版',
      description: savedStrategy.description,
      strategy: savedStrategy.strategy,
      backtestConfig: savedStrategy.backtestConfig
    })
    expect(apiClient.get).toHaveBeenCalledWith('/strategies', {
      params: { keyword: '', page: 1, pageSize: 10 }
    })
    expect(wrapper.text()).toContain('已重命名策略：五分钟突破策略新版')
  })

  it('shows custom block details and deletes after confirmation', async () => {
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
    expect(wrapper.text()).toContain('1 条连接')
    expect(wrapper.text()).toContain('买入 x1')
    expect(wrapper.text()).toContain('止损 x1')

    await wrapper.find('.custom-block-delete-button').trigger('click')

    expect(apiClient.delete).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('确认删除这个积木吗')

    await wrapper.find('.custom-block-confirm-delete-button').trigger('click')

    expect(apiClient.delete).toHaveBeenCalledWith('/custom-blocks/21')
    expect(apiClient.get).toHaveBeenCalledWith('/custom-blocks', {
      params: { keyword: '', page: 1, pageSize: 10 }
    })
  })

  it('opens a custom block template in the builder workspace', async () => {
    mockPersonalSpaceRequests()
    const wrapper = mount(PersonalSpaceView)

    await flushPromises()
    await wrapper.find('[data-space-tab="custom-blocks"]').trigger('click')
    await wrapper.find('.custom-block-use-button').trigger('click')

    const workspaceStore = useStrategyWorkspaceStore()
    expect(workspaceStore.pendingWorkspaceDraft?.source).toBe('custom-block-template')
    expect(workspaceStore.pendingWorkspaceDraft?.name).toBe('突破止盈模板')
    expect(workspaceStore.pendingWorkspaceDraft?.strategy.nodes[0].type).toBe('buy')
    expect(workspaceStore.pendingWorkspaceDraft?.backtestConfig).toBeNull()
    expect(pushMock).toHaveBeenCalledWith('/')
  })

  it('publishes a private custom block for review from personal space', async () => {
    mockPersonalSpaceRequests()
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { ...savedCustomBlock, reviewStatus: 'pending_review' }
    })
    const wrapper = mount(PersonalSpaceView)

    await flushPromises()
    await wrapper.find('[data-space-tab="custom-blocks"]').trigger('click')
    await wrapper.find('.custom-block-publish-button').trigger('click')
    await flushPromises()

    expect(apiClient.post).toHaveBeenCalledWith('/custom-blocks/21/publish')
    expect(wrapper.text()).toContain('已提交审核')
  })

  it('shows custom block publish actions by review status', async () => {
    mockPersonalSpaceRequests({
      customBlocks: [
        { ...savedCustomBlock, id: 21, reviewStatus: 'private' },
        { ...savedCustomBlock, id: 22, name: '待审核模板', reviewStatus: 'pending_review' },
        { ...savedCustomBlock, id: 23, name: '公开模板', reviewStatus: 'approved' },
        { ...savedCustomBlock, id: 24, name: '拒绝模板', reviewStatus: 'rejected' }
      ]
    })
    const wrapper = mount(PersonalSpaceView)

    await flushPromises()
    await wrapper.find('[data-space-tab="custom-blocks"]').trigger('click')

    expect(wrapper.text()).toContain('发布')
    expect(wrapper.text()).toContain('待审核')
    expect(wrapper.text()).toContain('已公开')
    expect(wrapper.text()).toContain('重新发布')
  })

  it('disambiguates duplicate custom block names in personal space', async () => {
    mockPersonalSpaceRequests({
      customBlocks: [
        { ...savedCustomBlock, id: 21, name: '未命名积木模板' },
        { ...savedCustomBlock, id: 22, name: '未命名积木模板' }
      ]
    })
    const wrapper = mount(PersonalSpaceView)

    await flushPromises()
    await wrapper.find('[data-space-tab="custom-blocks"]').trigger('click')

    expect(wrapper.text()).toContain('未命名积木模板 #21')
    expect(wrapper.text()).toContain('未命名积木模板 #22')
  })

  it('edits custom block metadata and handles duplicate names', async () => {
    mockPersonalSpaceRequests()
    vi.mocked(apiClient.put)
      .mockResolvedValueOnce({
        data: {
          ...savedCustomBlock,
          name: '突破止盈模板新版',
          category: '动作',
          description: '更新后的说明',
          tags: ['突破', '止盈']
        }
      })
      .mockRejectedValueOnce({ response: { status: 409 } })
    const wrapper = mount(PersonalSpaceView)

    await flushPromises()
    await wrapper.find('[data-space-tab="custom-blocks"]').trigger('click')
    await wrapper.find('.custom-block-edit-button').trigger('click')

    expect((wrapper.find('.custom-block-name-input').element as HTMLInputElement).value).toBe(
      '突破止盈模板'
    )
    expect((wrapper.find('.custom-block-category-input').element as HTMLInputElement).value).toBe(
      '风控'
    )

    await wrapper.find('.custom-block-name-input').setValue('突破止盈模板新版')
    await wrapper.find('.custom-block-category-input').setValue('动作')
    await wrapper.find('.custom-block-description-input').setValue('更新后的说明')
    await wrapper.find('.custom-block-tags-input').setValue('突破, 止盈')
    await wrapper.find('.custom-block-save-button').trigger('click')

    expect(apiClient.put).toHaveBeenCalledWith('/custom-blocks/21', {
      name: '突破止盈模板新版',
      description: '更新后的说明',
      category: '动作',
      tags: ['突破', '止盈'],
      template: savedCustomBlock.template
    })
    await flushPromises()

    await wrapper.find('.custom-block-edit-button').trigger('click')
    await wrapper.find('.custom-block-name-input').setValue('突破止盈模板')
    await wrapper.find('.custom-block-save-button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('已存在同名积木，请换一个名称')
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
    expect(wrapper.text()).toContain('规则提示')
    expect(wrapper.text()).toContain('A股 T+1 规则限制')
    expect(wrapper.text()).toContain('策略执行时间线')
    expect(wrapper.text()).toContain('买入成交')
    expect(wrapper.text()).toContain('卖出信号被拦截')
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

  it('shows the selected market rules when creating a simulation account', async () => {
    mockPersonalSpaceRequests()
    const wrapper = mount(PersonalSpaceView)

    await flushPromises()
    await wrapper.find('[data-space-tab="accounts"]').trigger('click')

    expect(apiClient.get).toHaveBeenCalledWith('/market-rules')
    expect(wrapper.text()).toContain('当前按 A股 规则模拟')
    expect(wrapper.text()).toContain('T+1')
    expect(wrapper.text()).toContain('每笔买入 100 股')
    expect(wrapper.text()).toContain('涨跌停 10%')
    expect(wrapper.text()).toContain('09:30-11:30')

    await wrapper.find('.account-market-select').setValue('US_STOCK')
    await nextTick()

    expect(wrapper.text()).toContain('当前按 美股 规则模拟')
    expect(wrapper.text()).toContain('每笔买入 1 股')
    expect(wrapper.text()).toContain('日内买卖')
    expect(wrapper.text()).toContain('无固定涨跌停')
    expect(wrapper.text()).toContain('09:30-16:00')
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
      if (url === '/market-rules') {
        return Promise.resolve({ data: { items: marketRules } })
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
