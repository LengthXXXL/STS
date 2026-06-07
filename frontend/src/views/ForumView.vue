<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { apiClient } from '../api/http'
import { useAuthStore } from '../stores/auth'

interface ForumPostItem {
  id: number
  authorId: number
  authorName: string
  title: string
  content: string
  topic: string
  sharedBlockId: number | null
  reviewStatus: 'approved' | 'pending_review' | 'rejected'
  commentCount: number
  createdAt: string
  updatedAt: string
}

interface ForumComment {
  id: number
  postId: number
  authorId: number
  authorName: string
  content: string
  reviewStatus: 'approved' | 'pending_review' | 'rejected'
  createdAt: string
  updatedAt: string
}

interface ForumPostDetail extends ForumPostItem {
  comments: ForumComment[]
}

interface ForumPostListResponse {
  items: ForumPostItem[]
  total: number
  page: number
  pageSize: number
}

const authStore = useAuthStore()
const posts = ref<ForumPostItem[]>([])
const selectedPost = ref<ForumPostDetail | null>(null)
const keyword = ref('')
const page = ref(1)
const pageSize = 10
const total = ref(0)
const loading = ref(false)
const detailLoading = ref(false)
const error = ref('')
const status = ref('')
const postTitle = ref('')
const postTopic = ref('积木经验')
const postContent = ref('')
const commentContent = ref('')

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

function requireLogin() {
  window.dispatchEvent(new CustomEvent('sts:auth-required'))
}

async function loadPosts() {
  loading.value = true
  error.value = ''
  try {
    const response = await apiClient.get<ForumPostListResponse>('/forum/posts', {
      params: {
        keyword: keyword.value.trim(),
        page: page.value,
        pageSize
      }
    })
    posts.value = response.data.items
    total.value = response.data.total
  } catch {
    error.value = '论坛帖子加载失败'
  } finally {
    loading.value = false
  }
}

async function searchPosts() {
  page.value = 1
  await loadPosts()
}

async function openPost(post: ForumPostItem) {
  detailLoading.value = true
  error.value = ''
  try {
    const response = await apiClient.get<ForumPostDetail>(`/forum/posts/${post.id}`)
    selectedPost.value = response.data
  } catch {
    error.value = '帖子详情加载失败'
  } finally {
    detailLoading.value = false
  }
}

async function submitPost() {
  if (!authStore.isAuthenticated) {
    requireLogin()
    return
  }

  const title = postTitle.value.trim()
  const content = postContent.value.trim()
  const topic = postTopic.value.trim() || '交流'
  if (!title || !content) {
    status.value = '请填写帖子标题和正文'
    return
  }

  await apiClient.post('/forum/posts', {
    title,
    topic,
    content,
    sharedBlockId: null
  })
  postTitle.value = ''
  postContent.value = ''
  postTopic.value = '积木经验'
  status.value = '帖子已提交审核'
}

async function submitComment() {
  if (!authStore.isAuthenticated) {
    requireLogin()
    return
  }
  if (!selectedPost.value) {
    return
  }

  const content = commentContent.value.trim()
  if (!content) {
    status.value = '请填写评论内容'
    return
  }

  await apiClient.post(`/forum/posts/${selectedPost.value.id}/comments`, { content })
  commentContent.value = ''
  status.value = '评论已提交审核'
}

async function changePage(nextPage: number) {
  if (nextPage < 1 || nextPage > totalPages.value || nextPage === page.value) {
    return
  }
  page.value = nextPage
  await loadPosts()
}

function formatDate(value: string) {
  return value.slice(0, 10)
}

onMounted(() => {
  void loadPosts()
})
</script>

<template>
  <section class="forum-page">
    <header class="forum-header">
      <div>
        <h1>论坛</h1>
        <p>分享交易策略、回测结果和积木使用经验。帖子与评论提交后会进入审核。</p>
      </div>
      <form class="forum-search" @submit.prevent="searchPosts">
        <input v-model="keyword" class="forum-search-input" placeholder="搜索帖子" />
        <button class="forum-search-button" type="button" @click="searchPosts">搜索</button>
      </form>
    </header>

    <section class="forum-composer">
      <div>
        <strong>发布新帖</strong>
        <p>写下策略思路、回测结论或积木组合经验。</p>
      </div>
      <input v-model="postTitle" class="forum-post-title-input" placeholder="帖子标题" />
      <input v-model="postTopic" class="forum-post-topic-input" placeholder="主题，例如：积木经验" />
      <textarea
        v-model="postContent"
        class="forum-post-content-input"
        placeholder="正文内容"
      ></textarea>
      <button class="forum-post-submit-button" type="button" @click="submitPost">提交审核</button>
    </section>

    <p v-if="error" class="form-error">{{ error }}</p>
    <p v-if="status" class="space-muted">{{ status }}</p>

    <div class="forum-layout">
      <section class="forum-post-list">
        <p v-if="loading" class="space-muted">正在加载帖子</p>
        <p v-else-if="posts.length === 0" class="space-muted">暂无公开帖子</p>
        <article v-for="post in posts" v-else :key="post.id" class="forum-post-item">
          <div class="forum-post-topic">{{ post.topic }}</div>
          <div>
            <h2>{{ post.title }}</h2>
            <p>{{ post.content }}</p>
            <small>
              作者 {{ post.authorName }} · 评论 {{ post.commentCount }} ·
              {{ formatDate(post.updatedAt) }}
            </small>
          </div>
          <button class="forum-post-detail-button" type="button" @click="openPost(post)">
            查看
          </button>
        </article>

        <footer class="space-footer">
          <span>共 {{ total }} 个公开帖子</span>
          <div class="space-pagination">
            <button type="button" :disabled="page <= 1" @click="changePage(page - 1)">
              上一页
            </button>
            <span>第 {{ page }} / {{ totalPages }} 页</span>
            <button type="button" :disabled="page >= totalPages" @click="changePage(page + 1)">
              下一页
            </button>
          </div>
        </footer>
      </section>

      <aside class="forum-thread-panel">
        <p v-if="detailLoading" class="space-muted">正在加载帖子详情</p>
        <template v-else-if="selectedPost">
          <div class="forum-thread-main">
            <span>{{ selectedPost.topic }}</span>
            <h2>{{ selectedPost.title }}</h2>
            <p>{{ selectedPost.content }}</p>
            <small>
              作者 {{ selectedPost.authorName }} · {{ formatDate(selectedPost.updatedAt) }}
            </small>
          </div>
          <div class="forum-comments">
            <strong>评论 {{ selectedPost.commentCount }}</strong>
            <p v-if="selectedPost.comments.length === 0" class="space-muted">暂无公开评论</p>
            <article
              v-for="comment in selectedPost.comments"
              v-else
              :key="comment.id"
              class="forum-comment-item"
            >
              <small>{{ comment.authorName }} · {{ formatDate(comment.updatedAt) }}</small>
              <p>{{ comment.content }}</p>
            </article>
          </div>
          <div class="forum-comment-form">
            <textarea
              v-model="commentContent"
              class="forum-comment-input"
              placeholder="写下你的评论"
            ></textarea>
            <button class="forum-comment-submit-button" type="button" @click="submitComment">
              提交评论审核
            </button>
          </div>
        </template>
        <p v-else class="space-muted">选择一个帖子查看详情和评论。</p>
      </aside>
    </div>
  </section>
</template>
