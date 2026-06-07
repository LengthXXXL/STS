<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { apiClient } from '../api/http'
import { useAuthStore } from '../stores/auth'

type ReviewTab = 'posts' | 'comments'

interface ForumPostReview {
  id: number
  authorId: number
  authorName: string
  title: string
  content: string
  topic: string
  sharedBlockId: number | null
  reviewStatus: 'pending_review' | 'approved' | 'rejected'
  reviewReason: string | null
  commentCount: number
  createdAt: string
  updatedAt: string
}

interface ForumCommentReview {
  id: number
  postId: number
  postTitle: string
  authorId: number
  authorName: string
  content: string
  reviewStatus: 'pending_review' | 'approved' | 'rejected'
  reviewReason: string | null
  createdAt: string
  updatedAt: string
}

interface ReviewListResponse<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
}

const authStore = useAuthStore()
const activeTab = ref<ReviewTab>('posts')
const keyword = ref('')
const postReviews = ref<ForumPostReview[]>([])
const commentReviews = ref<ForumCommentReview[]>([])
const postTotal = ref(0)
const commentTotal = ref(0)
const pageSize = 10
const postPage = ref(1)
const commentPage = ref(1)
const loading = ref(false)
const status = ref('')
const error = ref('')
const postRejectReasons = ref<Record<number, string>>({})
const commentRejectReasons = ref<Record<number, string>>({})

const isAdmin = computed(() => authStore.user?.roles.includes('admin') ?? false)
const activeTotal = computed(() =>
  activeTab.value === 'posts' ? postTotal.value : commentTotal.value
)
const postTotalPages = computed(() => Math.max(1, Math.ceil(postTotal.value / pageSize)))
const commentTotalPages = computed(() => Math.max(1, Math.ceil(commentTotal.value / pageSize)))

async function loadPostReviews() {
  const response = await apiClient.get<ReviewListResponse<ForumPostReview>>(
    '/admin/forum-post-reviews',
    {
      params: {
        keyword: activeTab.value === 'posts' ? keyword.value.trim() : '',
        page: postPage.value,
        pageSize
      }
    }
  )
  postReviews.value = response.data.items
  postTotal.value = response.data.total
}

async function loadCommentReviews() {
  const response = await apiClient.get<ReviewListResponse<ForumCommentReview>>(
    '/admin/forum-comment-reviews',
    {
      params: {
        keyword: activeTab.value === 'comments' ? keyword.value.trim() : '',
        page: commentPage.value,
        pageSize
      }
    }
  )
  commentReviews.value = response.data.items
  commentTotal.value = response.data.total
}

async function loadReviewQueues() {
  if (!isAdmin.value) {
    return
  }

  loading.value = true
  error.value = ''
  try {
    await Promise.all([loadPostReviews(), loadCommentReviews()])
  } catch {
    error.value = '审核队列加载失败'
  } finally {
    loading.value = false
  }
}

async function searchActiveQueue() {
  status.value = ''
  if (activeTab.value === 'posts') {
    postPage.value = 1
    await loadPostReviews()
    return
  }
  commentPage.value = 1
  await loadCommentReviews()
}

async function switchTab(tab: ReviewTab) {
  activeTab.value = tab
  status.value = ''
  error.value = ''
}

async function approvePost(post: ForumPostReview) {
  await apiClient.post(`/admin/forum-posts/${post.id}/approve`)
  status.value = '帖子已通过审核'
  await loadPostReviews()
}

async function rejectPost(post: ForumPostReview) {
  const reason = (postRejectReasons.value[post.id] ?? '').trim()
  if (!reason) {
    status.value = '请填写驳回原因'
    return
  }
  await apiClient.post(`/admin/forum-posts/${post.id}/reject`, { reason })
  delete postRejectReasons.value[post.id]
  status.value = '帖子已驳回'
  await loadPostReviews()
}

async function approveComment(comment: ForumCommentReview) {
  await apiClient.post(`/admin/forum-comments/${comment.id}/approve`)
  status.value = '评论已通过审核'
  await loadCommentReviews()
}

async function rejectComment(comment: ForumCommentReview) {
  const reason = (commentRejectReasons.value[comment.id] ?? '').trim()
  if (!reason) {
    status.value = '请填写驳回原因'
    return
  }
  await apiClient.post(`/admin/forum-comments/${comment.id}/reject`, { reason })
  delete commentRejectReasons.value[comment.id]
  status.value = '评论已驳回'
  await loadCommentReviews()
}

async function changePostPage(nextPage: number) {
  if (nextPage < 1 || nextPage > postTotalPages.value || nextPage === postPage.value) {
    return
  }
  postPage.value = nextPage
  await loadPostReviews()
}

async function changeCommentPage(nextPage: number) {
  if (
    nextPage < 1 ||
    nextPage > commentTotalPages.value ||
    nextPage === commentPage.value
  ) {
    return
  }
  commentPage.value = nextPage
  await loadCommentReviews()
}

function formatDate(value: string) {
  return value.slice(0, 10)
}

onMounted(loadReviewQueues)

watch(isAdmin, (nextValue, previousValue) => {
  if (nextValue && !previousValue) {
    void loadReviewQueues()
  }
})
</script>

<template>
  <section class="admin-review-page page-panel">
    <div v-if="!isAdmin" class="admin-review-denied">
      <p>仅管理员可访问审核管理。</p>
    </div>

    <template v-else>
      <header class="admin-review-header">
        <div>
          <p class="admin-review-eyebrow">内容审核</p>
          <h1>审核管理</h1>
          <p>处理论坛里待审核的帖子和评论，让公开内容保持清晰、可靠。</p>
        </div>
        <form class="admin-review-search" @submit.prevent="searchActiveQueue">
          <input v-model="keyword" placeholder="搜索当前队列" aria-label="搜索当前审核队列" />
          <button type="submit">搜索</button>
        </form>
      </header>

      <div class="admin-review-tabs" role="tablist" aria-label="审核队列">
        <button
          class="admin-review-post-tab"
          :class="{ 'admin-review-tab-active': activeTab === 'posts' }"
          type="button"
          @click="switchTab('posts')"
        >
          待审核帖子
          <span>{{ postTotal }}</span>
        </button>
        <button
          class="admin-review-comment-tab"
          :class="{ 'admin-review-tab-active': activeTab === 'comments' }"
          type="button"
          @click="switchTab('comments')"
        >
          待审核评论
          <span>{{ commentTotal }}</span>
        </button>
      </div>

      <p v-if="status" class="admin-review-status">{{ status }}</p>
      <p v-if="error" class="admin-review-error">{{ error }}</p>

      <div class="admin-review-summary">
        <span>当前队列 {{ activeTotal }} 条</span>
        <span v-if="loading">加载中</span>
      </div>

      <div v-if="activeTab === 'posts'" class="admin-review-list">
        <article v-for="post in postReviews" :key="post.id" class="admin-review-item">
          <div class="admin-review-item-main">
            <div class="admin-review-item-meta">
              <span>{{ post.topic }}</span>
              <span>作者 {{ post.authorName }}</span>
              <span>{{ formatDate(post.createdAt) }}</span>
            </div>
            <h2>{{ post.title }}</h2>
            <p>{{ post.content }}</p>
          </div>
          <div class="admin-review-item-actions">
            <textarea
              v-model="postRejectReasons[post.id]"
              class="admin-review-reason-input admin-review-post-reason-input"
              placeholder="填写驳回原因"
            ></textarea>
            <button class="admin-review-post-approve" type="button" @click="approvePost(post)">
              通过
            </button>
            <button class="admin-review-post-reject" type="button" @click="rejectPost(post)">
              驳回
            </button>
          </div>
        </article>
        <p v-if="!postReviews.length && !loading" class="admin-review-empty">暂无待审核帖子。</p>
        <div class="admin-review-pagination">
          <button type="button" @click="changePostPage(postPage - 1)">上一页</button>
          <span>{{ postPage }} / {{ postTotalPages }}</span>
          <button type="button" @click="changePostPage(postPage + 1)">下一页</button>
        </div>
      </div>

      <div v-else class="admin-review-list">
        <article v-for="comment in commentReviews" :key="comment.id" class="admin-review-item">
          <div class="admin-review-item-main">
            <div class="admin-review-item-meta">
              <span>作者 {{ comment.authorName }}</span>
              <span>{{ formatDate(comment.createdAt) }}</span>
            </div>
            <h2>关联帖子：{{ comment.postTitle }}</h2>
            <p>{{ comment.content }}</p>
          </div>
          <div class="admin-review-item-actions">
            <textarea
              v-model="commentRejectReasons[comment.id]"
              class="admin-review-reason-input admin-review-comment-reason-input"
              placeholder="填写驳回原因"
            ></textarea>
            <button
              class="admin-review-comment-approve"
              type="button"
              @click="approveComment(comment)"
            >
              通过
            </button>
            <button
              class="admin-review-comment-reject"
              type="button"
              @click="rejectComment(comment)"
            >
              驳回
            </button>
          </div>
        </article>
        <p v-if="!commentReviews.length && !loading" class="admin-review-empty">
          暂无待审核评论。
        </p>
        <div class="admin-review-pagination">
          <button type="button" @click="changeCommentPage(commentPage - 1)">上一页</button>
          <span>{{ commentPage }} / {{ commentTotalPages }}</span>
          <button type="button" @click="changeCommentPage(commentPage + 1)">下一页</button>
        </div>
      </div>
    </template>
  </section>
</template>
