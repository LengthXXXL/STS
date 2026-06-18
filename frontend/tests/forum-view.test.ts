import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiClient } from '../src/api/http'
import { useAuthStore } from '../src/stores/auth'
import { useStrategyWorkspaceStore } from '../src/stores/strategyWorkspace'
import ForumView from '../src/views/ForumView.vue'

const routeMock = vi.hoisted(() => ({
  query: {} as Record<string, string>
}))
const routerReplaceMock = vi.hoisted(() => vi.fn())
const routerPushMock = vi.hoisted(() => vi.fn())

vi.mock('vue-router', () => ({
  useRoute: () => routeMock,
  useRouter: () => ({
    replace: routerReplaceMock,
    push: routerPushMock
  })
}))

vi.mock('../src/api/http', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn()
  }
}))

enableAutoUnmount(afterEach)

const forumPost = {
  id: 12,
  authorId: 1,
  authorName: 'alice',
  title: '止盈积木复盘',
  content: '这个帖子记录一次止盈积木的使用经验。',
  topic: '积木经验',
  sharedBlockId: null,
  relatedType: null,
  relatedId: null,
  relatedTitle: null,
  relatedSummary: null,
  reviewStatus: 'approved',
  attachments: [],
  commentCount: 1,
  likeCount: 2,
  favoriteCount: 1,
  isLiked: false,
  isFavorited: false,
  createdAt: '2026-06-07T10:00:00',
  updatedAt: '2026-06-07T10:00:00'
}

const forumAttachment = {
  id: 61,
  fileId: 51,
  originalName: '策略说明.json',
  contentType: 'application/json',
  size: 2048,
  downloadUrl: '/api/forum/posts/12/attachments/51/download'
}

const savedFile = {
  id: 51,
  originalName: '策略说明.json',
  contentType: 'application/json',
  size: 2048
}

const forumDetail = {
  ...forumPost,
  attachments: [],
  comments: [
    {
      id: 21,
      postId: 12,
      authorId: 2,
      authorName: 'bob',
      content: '这个案例很适合新手复盘。',
      reviewStatus: 'approved',
      createdAt: '2026-06-07T11:00:00',
      updatedAt: '2026-06-07T11:00:00'
    }
  ]
}

const strategyDetail = {
  id: 31,
  name: '五分钟突破策略',
  description: '用于论坛关联',
  ownerId: 1,
  isPublic: false,
  createdAt: '2026-06-06T10:00:00',
  updatedAt: '2026-06-06T10:30:00',
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

function mockForum() {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === '/forum/posts') {
      return Promise.resolve({
        data: { items: [forumPost], total: 1, page: 1, pageSize: 10 }
      })
    }
    if (url === '/forum/posts/12') {
      return Promise.resolve({ data: forumDetail })
    }
    if (url === '/strategies') {
      return Promise.resolve({
        data: {
          items: [
            {
              id: 31,
              name: '五分钟突破策略',
              description: '用于论坛关联',
              backtestConfig: { symbol: '000001.SZ', timeframe: '5m' }
            }
          ],
          total: 1,
          page: 1,
          pageSize: 10
        }
      })
    }
    if (url === '/strategies/31') {
      return Promise.resolve({ data: strategyDetail })
    }
    if (url === '/backtests') {
      return Promise.resolve({ data: { items: [], total: 0, page: 1, pageSize: 10 } })
    }
    if (url === '/custom-blocks') {
      return Promise.resolve({ data: { items: [], total: 0, page: 1, pageSize: 10 } })
    }
    if (url === '/shared-blocks') {
      return Promise.resolve({ data: { items: [], total: 0, page: 1, pageSize: 10 } })
    }
    if (url === '/files') {
      return Promise.resolve({ data: { items: [savedFile], total: 1, page: 1, pageSize: 10 } })
    }
    return Promise.reject(new Error(`Unhandled GET ${url}`))
  })
}

describe('forum view', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    routeMock.query = {}
    routerReplaceMock.mockReset()
    routerPushMock.mockReset()
    vi.clearAllMocks()
  })

  it('loads public forum posts and opens a detail thread', async () => {
    mockForum()
    const wrapper = mount(ForumView)
    await flushPromises()

    expect(apiClient.get).toHaveBeenCalledWith('/forum/posts', {
      params: { keyword: '', sort: 'latest_reply', page: 1, pageSize: 10 }
    })
    expect(wrapper.text()).toContain('止盈积木复盘')
    expect(wrapper.text()).toContain('alice')
    expect(wrapper.text()).toContain('评论 1')
    expect(wrapper.text()).toContain('点赞 2')
    expect(wrapper.text()).toContain('收藏 1')
    expect(wrapper.text()).toContain('第 1 / 1 页 · 每页 10 条')

    await wrapper.find('.forum-post-detail-button').trigger('click')
    await flushPromises()

    expect(apiClient.get).toHaveBeenCalledWith('/forum/posts/12')
    expect(routerReplaceMock).toHaveBeenCalledWith({ name: 'forum', query: { postId: '12' } })
    expect(wrapper.find('.forum-thread-panel').exists()).toBe(false)
    expect(wrapper.find('.forum-post-item.is-expanded .forum-inline-thread-panel').exists()).toBe(true)
    expect(wrapper.text()).toContain('这个案例很适合新手复盘。')

    await wrapper.find('.forum-thread-close-button').trigger('click')

    expect(wrapper.find('.forum-inline-thread-panel').exists()).toBe(false)
    expect(routerReplaceMock).toHaveBeenCalledWith({ name: 'forum', query: {} })
  })

  it('changes public forum sorting without losing pagination state clarity', async () => {
    mockForum()
    const wrapper = mount(ForumView)
    await flushPromises()

    await wrapper.find('.forum-sort-select').setValue('most_commented')
    await flushPromises()

    expect(apiClient.get).toHaveBeenLastCalledWith('/forum/posts', {
      params: { keyword: '', sort: 'most_commented', page: 1, pageSize: 10 }
    })
    expect(wrapper.text()).toContain('最多评论')
    expect(wrapper.text()).toContain('第 1 / 1 页 · 每页 10 条')
  })

  it('likes, favorites, unlikes, and unfavorites a forum post when logged in', async () => {
    mockForum()
    vi.mocked(apiClient.post)
      .mockResolvedValueOnce({ data: { ...forumDetail, isLiked: true, likeCount: 3 } })
      .mockResolvedValueOnce({
        data: { ...forumDetail, isLiked: true, likeCount: 3, isFavorited: true, favoriteCount: 2 }
      })
    vi.mocked(apiClient.delete).mockResolvedValue({ data: undefined })
    const authStore = useAuthStore()
    authStore.setSession({
      token: 'token-123',
      user: { id: 2, username: 'bob', email: 'bob@example.com', roles: ['user'] }
    })
    const wrapper = mount(ForumView)
    await flushPromises()

    await wrapper.find('.forum-post-like-button').trigger('click')
    await flushPromises()

    expect(apiClient.post).toHaveBeenCalledWith('/forum/posts/12/like')
    expect(wrapper.text()).toContain('已赞 3')

    await wrapper.find('.forum-post-favorite-button').trigger('click')
    await flushPromises()

    expect(apiClient.post).toHaveBeenCalledWith('/forum/posts/12/favorite')
    expect(wrapper.text()).toContain('已收藏 2')

    await wrapper.find('.forum-post-like-button').trigger('click')
    await wrapper.find('.forum-post-favorite-button').trigger('click')
    await flushPromises()

    expect(apiClient.delete).toHaveBeenCalledWith('/forum/posts/12/like')
    expect(apiClient.delete).toHaveBeenCalledWith('/forum/posts/12/favorite')
    expect(wrapper.text()).toContain('点赞 2')
    expect(wrapper.text()).toContain('收藏 1')
  })

  it('asks visitors to log in before liking or favoriting', async () => {
    mockForum()
    const authRequired = vi.fn()
    window.addEventListener('sts:auth-required', authRequired)
    const wrapper = mount(ForumView)
    await flushPromises()

    await wrapper.find('.forum-post-like-button').trigger('click')
    await wrapper.find('.forum-post-favorite-button').trigger('click')
    await nextTick()

    expect(authRequired).toHaveBeenCalledTimes(2)
    expect(apiClient.post).not.toHaveBeenCalled()
    expect(apiClient.delete).not.toHaveBeenCalled()
    window.removeEventListener('sts:auth-required', authRequired)
  })

  it('opens a forum detail from the postId route query', async () => {
    routeMock.query = { postId: '12' }
    mockForum()
    const wrapper = mount(ForumView)
    await flushPromises()

    expect(apiClient.get).toHaveBeenCalledWith('/forum/posts/12')
    expect(wrapper.find('.forum-post-item.is-expanded .forum-inline-thread-panel').exists()).toBe(true)
    expect(wrapper.text()).toContain('这个案例很适合新手复盘。')
  })

  it('submits a post and marks it pending review when logged in', async () => {
    mockForum()
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { ...forumPost, id: 13, title: '移动止损经验', reviewStatus: 'pending_review' }
    })
    const authStore = useAuthStore()
    authStore.setSession({
      token: 'token-123',
      user: { id: 2, username: 'bob', email: 'bob@example.com', roles: ['user'] }
    })
    const wrapper = mount(ForumView)
    await flushPromises()

    expect(wrapper.find('.forum-post-topic-input').attributes('placeholder')).toBe(
      '帖子分类，例如：策略复盘、回测问题、积木组合'
    )
    expect((wrapper.find('.forum-post-topic-input').element as HTMLInputElement).value).toBe('')

    await wrapper.find('.forum-post-title-input').setValue('移动止损经验')
    await wrapper.find('.forum-post-topic-input').setValue('策略复盘')
    await wrapper.find('.forum-post-content-input').setValue('移动止损适合高波动盘中策略。')
    await wrapper.find('.forum-post-submit-button').trigger('click')
    await flushPromises()

    expect(apiClient.post).toHaveBeenCalledWith('/forum/posts', {
      title: '移动止损经验',
      topic: '策略复盘',
      content: '移动止损适合高波动盘中策略。',
      sharedBlockId: null,
      attachmentFileIds: []
    })
    expect(wrapper.text()).toContain('帖子已提交审核，可在个人空间-我的论坛查看进度')
  })

  it('submits a post with a selected file attachment when logged in', async () => {
    mockForum()
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        ...forumPost,
        id: 15,
        title: '附件复盘',
        reviewStatus: 'pending_review',
        attachments: [forumAttachment]
      }
    })
    const authStore = useAuthStore()
    authStore.setSession({
      token: 'token-123',
      user: { id: 2, username: 'bob', email: 'bob@example.com', roles: ['user'] }
    })
    const wrapper = mount(ForumView)
    await flushPromises()

    expect(apiClient.get).toHaveBeenCalledWith('/files', {
      params: { page: 1, pageSize: 50 }
    })
    expect(wrapper.text()).toContain('策略说明.json')

    await wrapper.find('.forum-post-title-input').setValue('附件复盘')
    await wrapper.find('.forum-post-content-input').setValue('我想附上一份策略说明。')
    await wrapper.find('.forum-attachment-option input').setValue(true)
    await wrapper.find('.forum-post-submit-button').trigger('click')
    await flushPromises()

    expect(apiClient.post).toHaveBeenCalledWith('/forum/posts', {
      title: '附件复盘',
      topic: '交流',
      content: '我想附上一份策略说明。',
      sharedBlockId: null,
      attachmentFileIds: [51]
    })
  })

  it('submits a post with a selected strategy relation when logged in', async () => {
    mockForum()
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        ...forumPost,
        id: 14,
        title: '关联策略复盘',
        reviewStatus: 'pending_review',
        relatedType: 'strategy',
        relatedId: 31,
        relatedTitle: '五分钟突破策略',
        relatedSummary: '策略 · 000001.SZ · 5分钟'
      }
    })
    const authStore = useAuthStore()
    authStore.setSession({
      token: 'token-123',
      user: { id: 2, username: 'bob', email: 'bob@example.com', roles: ['user'] }
    })
    const wrapper = mount(ForumView)
    await flushPromises()

    await wrapper.find('.forum-post-title-input').setValue('关联策略复盘')
    await wrapper.find('.forum-post-content-input').setValue('我想分享这个策略的使用经验。')
    await wrapper.find('.forum-related-type-select').setValue('strategy')
    await nextTick()
    await wrapper.find('.forum-related-id-select').setValue('31')
    await wrapper.find('.forum-post-submit-button').trigger('click')
    await flushPromises()

    expect(apiClient.post).toHaveBeenCalledWith('/forum/posts', {
      title: '关联策略复盘',
      topic: '交流',
      content: '我想分享这个策略的使用经验。',
      sharedBlockId: null,
      attachmentFileIds: [],
      relatedType: 'strategy',
      relatedId: 31
    })
  })

  it('renders attachment chips and attachment cards in a forum detail thread', async () => {
    const detailWithAttachment = {
      ...forumDetail,
      attachments: [forumAttachment]
    }
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === '/forum/posts') {
        return Promise.resolve({
          data: {
            items: [{ ...forumPost, attachments: [forumAttachment] }],
            total: 1,
            page: 1,
            pageSize: 10
          }
        })
      }
      if (url === '/forum/posts/12') {
        return Promise.resolve({ data: detailWithAttachment })
      }
      return Promise.reject(new Error(`Unhandled GET ${url}`))
    })
    const wrapper = mount(ForumView)
    await flushPromises()

    expect(wrapper.text()).toContain('附件 1')

    await wrapper.find('.forum-post-detail-button').trigger('click')
    await flushPromises()

    expect(wrapper.find('.forum-attachment-card').exists()).toBe(true)
    expect(wrapper.text()).toContain('策略说明.json')
    expect(wrapper.text()).toContain('2 KB')
  })

  it('renders a related content card in a forum detail thread', async () => {
    const relatedDetail = {
      ...forumDetail,
      relatedType: 'strategy',
      relatedId: 31,
      relatedTitle: '五分钟突破策略',
      relatedSummary: '策略 · 000001.SZ · 5分钟'
    }
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === '/forum/posts') {
        return Promise.resolve({
          data: {
            items: [
              {
                ...forumPost,
                relatedType: 'strategy',
                relatedId: 31,
                relatedTitle: '五分钟突破策略',
                relatedSummary: '策略 · 000001.SZ · 5分钟'
              }
            ],
            total: 1,
            page: 1,
            pageSize: 10
          }
        })
      }
      if (url === '/forum/posts/12') {
        return Promise.resolve({ data: relatedDetail })
      }
      return Promise.reject(new Error(`Unhandled GET ${url}`))
    })
    const wrapper = mount(ForumView)
    await flushPromises()

    await wrapper.find('.forum-post-detail-button').trigger('click')
    await flushPromises()

    expect(wrapper.find('.forum-related-card').exists()).toBe(true)
    expect(wrapper.text()).toContain('关联内容')
    expect(wrapper.text()).toContain('五分钟突破策略')
    expect(wrapper.text()).toContain('策略 · 000001.SZ · 5分钟')
  })

  it('opens a related strategy card in the builder workspace', async () => {
    const relatedDetail = {
      ...forumDetail,
      relatedType: 'strategy',
      relatedId: 31,
      relatedTitle: '五分钟突破策略',
      relatedSummary: '策略 · 000001.SZ · 5分钟'
    }
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === '/forum/posts') {
        return Promise.resolve({
          data: { items: [{ ...forumPost, ...relatedDetail }], total: 1, page: 1, pageSize: 10 }
        })
      }
      if (url === '/forum/posts/12') {
        return Promise.resolve({ data: relatedDetail })
      }
      if (url === '/strategies/31') {
        return Promise.resolve({ data: strategyDetail })
      }
      return Promise.resolve({ data: { items: [], total: 0, page: 1, pageSize: 10 } })
    })
    const wrapper = mount(ForumView)
    await flushPromises()

    await wrapper.find('.forum-post-detail-button').trigger('click')
    await flushPromises()
    await wrapper.find('.forum-related-open-button').trigger('click')
    await flushPromises()

    const workspaceStore = useStrategyWorkspaceStore()
    expect(apiClient.get).toHaveBeenCalledWith('/strategies/31')
    expect(workspaceStore.pendingWorkspaceDraft?.source).toBe('saved-strategy')
    expect(workspaceStore.pendingWorkspaceDraft?.name).toBe('五分钟突破策略')
    expect(routerPushMock).toHaveBeenCalledWith('/')
  })

  it('routes a related backtest card to personal space detail', async () => {
    const relatedDetail = {
      ...forumDetail,
      relatedType: 'backtest',
      relatedId: 11,
      relatedTitle: '000001.SZ 5m 回测',
      relatedSummary: '收益 7.35% · 最大回撤 2.1%'
    }
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === '/forum/posts') {
        return Promise.resolve({
          data: { items: [{ ...forumPost, ...relatedDetail }], total: 1, page: 1, pageSize: 10 }
        })
      }
      if (url === '/forum/posts/12') {
        return Promise.resolve({ data: relatedDetail })
      }
      return Promise.resolve({ data: { items: [], total: 0, page: 1, pageSize: 10 } })
    })
    const wrapper = mount(ForumView)
    await flushPromises()

    await wrapper.find('.forum-post-detail-button').trigger('click')
    await flushPromises()
    await wrapper.find('.forum-related-open-button').trigger('click')

    expect(routerPushMock).toHaveBeenCalledWith({
      name: 'space',
      query: { tab: 'backtests', backtestId: '11' }
    })
  })

  it('routes a related shared block card to the shared block detail', async () => {
    const relatedDetail = {
      ...forumDetail,
      relatedType: 'shared_block',
      relatedId: 31,
      relatedTitle: '公开止盈模板',
      relatedSummary: '公开积木 · 风控 · 2 个积木'
    }
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === '/forum/posts') {
        return Promise.resolve({
          data: { items: [{ ...forumPost, ...relatedDetail }], total: 1, page: 1, pageSize: 10 }
        })
      }
      if (url === '/forum/posts/12') {
        return Promise.resolve({ data: relatedDetail })
      }
      return Promise.resolve({ data: { items: [], total: 0, page: 1, pageSize: 10 } })
    })
    const wrapper = mount(ForumView)
    await flushPromises()

    await wrapper.find('.forum-post-detail-button').trigger('click')
    await flushPromises()
    await wrapper.find('.forum-related-open-button').trigger('click')

    expect(routerPushMock).toHaveBeenCalledWith({
      name: 'shared-blocks',
      query: { blockId: '31' }
    })
  })

  it('asks visitors to log in before posting or commenting', async () => {
    mockForum()
    const authRequired = vi.fn()
    window.addEventListener('sts:auth-required', authRequired)
    const wrapper = mount(ForumView)
    await flushPromises()

    await wrapper.find('.forum-post-submit-button').trigger('click')
    await wrapper.find('.forum-post-detail-button').trigger('click')
    await flushPromises()
    await wrapper.find('.forum-comment-submit-button').trigger('click')
    await nextTick()

    expect(authRequired).toHaveBeenCalledTimes(2)
    expect(apiClient.post).not.toHaveBeenCalled()
    window.removeEventListener('sts:auth-required', authRequired)
  })

  it('submits a comment for review when logged in', async () => {
    mockForum()
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        id: 22,
        postId: 12,
        authorId: 2,
        authorName: 'bob',
        content: '我也想试试这个积木组合。',
        reviewStatus: 'pending_review',
        createdAt: '2026-06-07T12:00:00',
        updatedAt: '2026-06-07T12:00:00'
      }
    })
    const authStore = useAuthStore()
    authStore.setSession({
      token: 'token-123',
      user: { id: 2, username: 'bob', email: 'bob@example.com', roles: ['user'] }
    })
    const wrapper = mount(ForumView)
    await flushPromises()

    await wrapper.find('.forum-post-detail-button').trigger('click')
    await flushPromises()
    await wrapper.find('.forum-comment-input').setValue('我也想试试这个积木组合。')
    await wrapper.find('.forum-comment-submit-button').trigger('click')
    await flushPromises()

    expect(apiClient.post).toHaveBeenCalledWith('/forum/posts/12/comments', {
      content: '我也想试试这个积木组合。'
    })
    expect(wrapper.text()).toContain('评论已提交审核，可在个人空间-我的论坛查看进度')
  })
})
