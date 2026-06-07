import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiClient } from '../src/api/http'
import { useAuthStore } from '../src/stores/auth'
import ForumView from '../src/views/ForumView.vue'

const routeMock = vi.hoisted(() => ({
  query: {} as Record<string, string>
}))
const routerReplaceMock = vi.hoisted(() => vi.fn())

vi.mock('vue-router', () => ({
  useRoute: () => routeMock,
  useRouter: () => ({
    replace: routerReplaceMock
  })
}))

vi.mock('../src/api/http', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn()
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
  reviewStatus: 'approved',
  commentCount: 1,
  createdAt: '2026-06-07T10:00:00',
  updatedAt: '2026-06-07T10:00:00'
}

const forumDetail = {
  ...forumPost,
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
    return Promise.reject(new Error(`Unhandled GET ${url}`))
  })
}

describe('forum view', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    routeMock.query = {}
    routerReplaceMock.mockReset()
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
    expect(wrapper.text()).toContain('第 1 / 1 页 · 每页 10 条')

    await wrapper.find('.forum-post-detail-button').trigger('click')
    await flushPromises()

    expect(apiClient.get).toHaveBeenCalledWith('/forum/posts/12')
    expect(routerReplaceMock).toHaveBeenCalledWith({ name: 'forum', query: { postId: '12' } })
    expect(wrapper.find('.forum-thread-panel').exists()).toBe(true)
    expect(wrapper.text()).toContain('这个案例很适合新手复盘。')

    await wrapper.find('.forum-thread-close-button').trigger('click')

    expect(wrapper.text()).toContain('选择一个帖子查看详情和评论。')
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

  it('opens a forum detail from the postId route query', async () => {
    routeMock.query = { postId: '12' }
    mockForum()
    const wrapper = mount(ForumView)
    await flushPromises()

    expect(apiClient.get).toHaveBeenCalledWith('/forum/posts/12')
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

    await wrapper.find('.forum-post-title-input').setValue('移动止损经验')
    await wrapper.find('.forum-post-topic-input').setValue('策略复盘')
    await wrapper.find('.forum-post-content-input').setValue('移动止损适合高波动盘中策略。')
    await wrapper.find('.forum-post-submit-button').trigger('click')
    await flushPromises()

    expect(apiClient.post).toHaveBeenCalledWith('/forum/posts', {
      title: '移动止损经验',
      topic: '策略复盘',
      content: '移动止损适合高波动盘中策略。',
      sharedBlockId: null
    })
    expect(wrapper.text()).toContain('帖子已提交审核，可在个人空间-我的论坛查看进度')
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
