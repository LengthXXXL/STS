import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiClient } from '../src/api/http'
import { useAuthStore } from '../src/stores/auth'
import SharedBlocksView from '../src/views/SharedBlocksView.vue'

vi.mock('../src/api/http', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn()
  }
}))

const sharedBlock = {
  id: 31,
  ownerId: 1,
  authorName: 'alice',
  name: '公开止盈模板',
  description: '按收益目标退出',
  category: '风控',
  tags: ['止盈', '基础'],
  reviewStatus: 'approved',
  nodeCount: 2,
  connectionCount: 1,
  viewCount: 8,
  favoriteCount: 3,
  importCount: 2,
  isFavorited: false,
  createdAt: '2026-06-06T11:00:00',
  updatedAt: '2026-06-06T11:30:00'
}

const sharedBlockDetail = {
  ...sharedBlock,
  template: {
    version: 1,
    nodes: [
      {
        id: 'buy-1',
        type: 'buy',
        label: '买入',
        x: 0,
        y: 0,
        params: { sizePercent: '20' }
      },
      {
        id: 'take-profit-1',
        type: 'take-profit',
        label: '止盈',
        x: 200,
        y: 0,
        params: { profitRate: '5' }
      }
    ],
    edges: [{ id: 'edge-1', from: 'buy-1', to: 'take-profit-1' }],
    viewport: { x: 0, y: 0, scale: 1 }
  }
}

function mockSharedBlocks() {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === '/shared-blocks') {
      return Promise.resolve({
        data: { items: [sharedBlock], total: 1, page: 1, pageSize: 10 }
      })
    }
    if (url === '/shared-blocks/31') {
      return Promise.resolve({ data: sharedBlockDetail })
    }
    return Promise.reject(new Error(`Unhandled GET ${url}`))
  })
}

describe('shared blocks view', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('loads shared blocks and filters with query params', async () => {
    mockSharedBlocks()
    const wrapper = mount(SharedBlocksView)
    await flushPromises()

    expect(apiClient.get).toHaveBeenCalledWith('/shared-blocks', {
      params: { keyword: '', category: '', tag: '', sort: 'latest', page: 1, pageSize: 10 }
    })
    expect(wrapper.text()).toContain('公开止盈模板')
    expect(wrapper.text()).toContain('alice')
    expect(wrapper.text()).toContain('收藏 3')
    expect(wrapper.text()).toContain('导入 2')

    await wrapper.find('.shared-block-search-input').setValue('止盈')
    await wrapper.find('.shared-block-category-input').setValue('风控')
    await wrapper.find('.shared-block-tag-input').setValue('基础')
    await wrapper.find('.shared-block-sort-select').setValue('popular')
    await wrapper.find('.shared-block-search-button').trigger('click')

    expect(apiClient.get).toHaveBeenCalledWith('/shared-blocks', {
      params: {
        keyword: '止盈',
        category: '风控',
        tag: '基础',
        sort: 'popular',
        page: 1,
        pageSize: 10
      }
    })
  })

  it('opens details and imports a shared block when logged in', async () => {
    mockSharedBlocks()
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { id: 55, name: '公开止盈模板（导入）' }
    })
    const authStore = useAuthStore()
    authStore.setSession({
      token: 'token-123',
      user: { id: 2, username: 'bob', email: 'bob@example.com', roles: ['user'] }
    })
    const wrapper = mount(SharedBlocksView)
    await flushPromises()

    await wrapper.find('.shared-block-detail-button').trigger('click')
    await flushPromises()
    expect(apiClient.get).toHaveBeenCalledWith('/shared-blocks/31')
    expect(wrapper.text()).toContain('买入 x1')
    expect(wrapper.text()).toContain('止盈 x1')

    await wrapper.find('.shared-block-import-button').trigger('click')
    await flushPromises()

    expect(apiClient.post).toHaveBeenCalledWith('/shared-blocks/31/import')
    expect(wrapper.text()).toContain('已导入到我的积木：公开止盈模板（导入）')
  })

  it('favorites and unfavorites a shared block when logged in', async () => {
    mockSharedBlocks()
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { ...sharedBlockDetail, isFavorited: true, favoriteCount: 4 }
    })
    vi.mocked(apiClient.delete).mockResolvedValueOnce({ data: null })
    const authStore = useAuthStore()
    authStore.setSession({
      token: 'token-123',
      user: { id: 2, username: 'bob', email: 'bob@example.com', roles: ['user'] }
    })
    const wrapper = mount(SharedBlocksView)
    await flushPromises()

    await wrapper.find('.shared-block-favorite-button').trigger('click')
    await flushPromises()
    expect(apiClient.post).toHaveBeenCalledWith('/shared-blocks/31/favorite')
    expect(wrapper.text()).toContain('已收藏')

    await wrapper.find('.shared-block-favorite-button').trigger('click')
    await flushPromises()
    expect(apiClient.delete).toHaveBeenCalledWith('/shared-blocks/31/favorite')
  })

  it('asks visitors to log in before favorite or import', async () => {
    mockSharedBlocks()
    const authRequired = vi.fn()
    window.addEventListener('sts:auth-required', authRequired)
    const wrapper = mount(SharedBlocksView)
    await flushPromises()

    await wrapper.find('.shared-block-favorite-button').trigger('click')
    await wrapper.find('.shared-block-import-button').trigger('click')
    await nextTick()

    expect(authRequired).toHaveBeenCalledTimes(2)
    window.removeEventListener('sts:auth-required', authRequired)
  })

  it('lets admins review pending shared blocks', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === '/shared-blocks') {
        return Promise.resolve({
          data: { items: [sharedBlock], total: 1, page: 1, pageSize: 10 }
        })
      }
      if (url === '/admin/custom-block-reviews') {
        return Promise.resolve({
          data: {
            items: [{ ...sharedBlock, id: 41, name: '待审核模板', reviewStatus: 'pending_review' }],
            total: 1,
            page: 1,
            pageSize: 10
          }
        })
      }
      return Promise.reject(new Error(`Unhandled GET ${url}`))
    })
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { ...sharedBlockDetail, id: 41, name: '待审核模板', reviewStatus: 'approved' }
    })
    const authStore = useAuthStore()
    authStore.setSession({
      token: 'token-123',
      user: { id: 1, username: 'admin', email: 'admin@example.com', roles: ['admin'] }
    })
    const wrapper = mount(SharedBlocksView)
    await flushPromises()

    expect(wrapper.find('.shared-block-review-tab').exists()).toBe(true)
    await wrapper.find('.shared-block-review-tab').trigger('click')
    await flushPromises()

    expect(apiClient.get).toHaveBeenCalledWith('/admin/custom-block-reviews', {
      params: { keyword: '', page: 1, pageSize: 10 }
    })
    expect(wrapper.text()).toContain('待审核模板')

    await wrapper.find('.shared-block-approve-button').trigger('click')
    await flushPromises()

    expect(apiClient.post).toHaveBeenCalledWith('/admin/custom-block-reviews/41/approve')
    expect(wrapper.text()).toContain('审核已通过')
  })
})
