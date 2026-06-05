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

describe('personal space view', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('loads saved strategies and opens one in the builder workspace', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: {
        items: [savedStrategy],
        total: 1,
        page: 1,
        pageSize: 10
      }
    })
    const wrapper = mount(PersonalSpaceView)

    await flushPromises()

    expect(apiClient.get).toHaveBeenCalledWith('/strategies', {
      params: { keyword: '', page: 1, pageSize: 10 }
    })
    expect(wrapper.text()).toContain('五分钟突破策略')
    expect(wrapper.text()).toContain('000001.SZ')

    await wrapper.find('.strategy-open-button').trigger('click')

    const workspaceStore = useStrategyWorkspaceStore()
    expect(workspaceStore.pendingStrategy?.id).toBe(7)
    expect(workspaceStore.pendingStrategy?.strategy.nodes[0].type).toBe('buy')
    expect(pushMock).toHaveBeenCalledWith('/')
  })

  it('deletes a saved strategy from the list', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: {
        items: [savedStrategy],
        total: 1,
        page: 1,
        pageSize: 10
      }
    })
    vi.mocked(apiClient.delete).mockResolvedValueOnce({ data: null })
    const wrapper = mount(PersonalSpaceView)

    await flushPromises()
    await wrapper.find('.strategy-delete-button').trigger('click')

    expect(apiClient.delete).toHaveBeenCalledWith('/strategies/7')
    expect(apiClient.get).toHaveBeenCalledTimes(2)
  })
})
