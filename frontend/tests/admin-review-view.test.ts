import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { apiClient } from '../src/api/http'
import { useAuthStore } from '../src/stores/auth'
import AdminReviewView from '../src/views/AdminReviewView.vue'

vi.mock('../src/api/http', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn()
  }
}))

enableAutoUnmount(afterEach)

const pendingPost = {
  id: 11,
  authorId: 2,
  authorName: 'alice',
  title: '待审核止盈帖子',
  content: '这里是一段策略复盘正文。',
  topic: '策略交流',
  sharedBlockId: null,
  reviewStatus: 'pending_review',
  commentCount: 0,
  createdAt: '2026-06-07T11:00:00',
  updatedAt: '2026-06-07T11:30:00'
}

const pendingComment = {
  id: 21,
  postId: 11,
  postTitle: '待审核止盈帖子',
  authorId: 3,
  authorName: 'bob',
  content: '这条评论需要管理员审核。',
  reviewStatus: 'pending_review',
  createdAt: '2026-06-07T12:00:00',
  updatedAt: '2026-06-07T12:00:00'
}

function mockReviewLists() {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === '/admin/forum-post-reviews') {
      return Promise.resolve({
        data: { items: [pendingPost], total: 1, page: 1, pageSize: 10 }
      })
    }
    if (url === '/admin/forum-comment-reviews') {
      return Promise.resolve({
        data: { items: [pendingComment], total: 1, page: 1, pageSize: 10 }
      })
    }
    return Promise.reject(new Error(`Unhandled GET ${url}`))
  })
  vi.mocked(apiClient.post).mockResolvedValue({ data: {} })
}

describe('admin review view', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('blocks non-admin users from loading review queues', async () => {
    const authStore = useAuthStore()
    authStore.setSession({
      token: 'token-user',
      user: { id: 2, username: 'alice', email: 'alice@example.com', roles: ['user'] }
    })

    const wrapper = mount(AdminReviewView)
    await flushPromises()

    expect(wrapper.text()).toContain('仅管理员可访问审核管理')
    expect(apiClient.get).not.toHaveBeenCalled()
  })

  it('loads forum post and comment review queues for admins', async () => {
    mockReviewLists()
    const authStore = useAuthStore()
    authStore.setSession({
      token: 'token-admin',
      user: { id: 1, username: 'admin', email: 'admin@example.com', roles: ['admin'] }
    })

    const wrapper = mount(AdminReviewView)
    await flushPromises()

    expect(apiClient.get).toHaveBeenCalledWith('/admin/forum-post-reviews', {
      params: { keyword: '', page: 1, pageSize: 10 }
    })
    expect(apiClient.get).toHaveBeenCalledWith('/admin/forum-comment-reviews', {
      params: { keyword: '', page: 1, pageSize: 10 }
    })
    expect(wrapper.text()).toContain('待审核帖子')
    expect(wrapper.text()).toContain('待审核止盈帖子')
    expect(wrapper.text()).toContain('alice')

    await wrapper.find('.admin-review-comment-tab').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('这条评论需要管理员审核。')
    expect(wrapper.text()).toContain('关联帖子：待审核止盈帖子')
  })

  it('approves posts and rejects comments from the review page', async () => {
    mockReviewLists()
    const authStore = useAuthStore()
    authStore.setSession({
      token: 'token-admin',
      user: { id: 1, username: 'admin', email: 'admin@example.com', roles: ['admin'] }
    })
    const wrapper = mount(AdminReviewView)
    await flushPromises()

    await wrapper.find('.admin-review-post-approve').trigger('click')
    await flushPromises()

    expect(apiClient.post).toHaveBeenCalledWith('/admin/forum-posts/11/approve')
    expect(wrapper.text()).toContain('帖子已通过审核')

    await wrapper.find('.admin-review-comment-tab').trigger('click')
    await flushPromises()
    await wrapper.find('.admin-review-comment-reject').trigger('click')
    await flushPromises()

    expect(apiClient.post).toHaveBeenCalledWith('/admin/forum-comments/21/reject')
    expect(wrapper.text()).toContain('评论已驳回')
  })
})
