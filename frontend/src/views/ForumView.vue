<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiClient } from '../api/http'
import { useAuthStore } from '../stores/auth'
import { useStrategyWorkspaceStore } from '../stores/strategyWorkspace'

interface ForumPostItem {
  id: number
  authorId: number
  authorName: string
  title: string
  content: string
  topic: string
  sharedBlockId: number | null
  relatedType: ForumRelatedType | null
  relatedId: number | null
  relatedTitle: string | null
  relatedSummary: string | null
  reviewStatus: 'approved' | 'pending_review' | 'rejected'
  attachments?: ForumAttachment[]
  commentCount: number
  likeCount: number
  favoriteCount: number
  isLiked: boolean
  isFavorited: boolean
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
  attachments: ForumAttachment[]
  comments: ForumComment[]
}

interface ForumPostListResponse {
  items: ForumPostItem[]
  total: number
  page: number
  pageSize: number
}

type ForumRelatedType = 'strategy' | 'backtest' | 'custom_block' | 'shared_block'
type ForumRelatedTypeSelection = '' | ForumRelatedType

interface ForumRelatedOption {
  type: ForumRelatedType
  id: number
  title: string
  summary: string
}

interface StrategyOptionResponse {
  id: number
  name: string
  backtestConfig?: {
    symbol?: string
    timeframe?: string
  } | null
}

interface StrategyDetailResponse extends StrategyOptionResponse {
  description: string | null
  ownerId: number
  isPublic: boolean
  createdAt: string
  updatedAt: string
  strategy: {
    version: 1
    nodes: Array<{
      id: string
      type: string
      label: string
      x: number
      y: number
      params: Record<string, string>
    }>
    edges: Array<{ id: string; from: string; to: string }>
    viewport: { x: number; y: number; scale: number }
  }
  backtestConfig: {
    market: 'A_SHARE' | 'US_STOCK'
    symbol: string
    timeframe: '5m' | '1m'
    startDate: string
    endDate: string
    initialCash: number
    simulationAccountId?: number
  } | null
}

interface BacktestOptionResponse {
  id: number
  symbol: string
  timeframe: string
  totalReturnPercent: number
  maxDrawdownPercent: number
}

interface CustomBlockOptionResponse {
  id: number
  name: string
  category: string
  template?: {
    nodes?: unknown[]
  }
}

interface CustomBlockDetailResponse extends CustomBlockOptionResponse {
  description: string | null
  template: StrategyDetailResponse['strategy']
}

interface SharedBlockOptionResponse {
  id: number
  name: string
  category: string
  nodeCount: number
}

interface ForumAttachment {
  id: number
  fileId: number
  originalName: string
  contentType: string
  size: number
  downloadUrl: string
}

interface UploadedFileOptionResponse {
  id: number
  originalName: string
  contentType: string
  size: number
}

const authStore = useAuthStore()
const workspaceStore = useStrategyWorkspaceStore()
const route = useRoute()
const router = useRouter()
const posts = ref<ForumPostItem[]>([])
const selectedPost = ref<ForumPostDetail | null>(null)
const keyword = ref('')
const topicFilter = ref('')
const authorFilter = ref('')
const relatedTypeFilter = ref<ForumRelatedTypeSelection>('')
const sort = ref<'latest_reply' | 'newest' | 'most_commented'>('latest_reply')
const page = ref(1)
const pageSize = 10
const total = ref(0)
const loading = ref(false)
const detailLoading = ref(false)
const detailLoadingPostId = ref<number | null>(null)
const error = ref('')
const status = ref('')
const postTitle = ref('')
const postTopic = ref('')
const postContent = ref('')
const commentContent = ref('')
const postAttachmentIds = ref<number[]>([])
const attachmentOptions = ref<UploadedFileOptionResponse[]>([])
const relatedType = ref<ForumRelatedTypeSelection>('')
const relatedId = ref('')
const relatedOptions = ref<Record<ForumRelatedType, ForumRelatedOption[]>>({
  strategy: [],
  backtest: [],
  custom_block: [],
  shared_block: []
})
const relatedOptionsLoading = ref(false)
const relatedOptionsError = ref('')
const attachmentOptionsError = ref('')

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const selectedRelatedOptions = computed(() =>
  relatedType.value === '' ? [] : relatedOptions.value[relatedType.value]
)

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
        topic: topicFilter.value.trim(),
        author: authorFilter.value.trim(),
        relatedType: relatedTypeFilter.value,
        sort: sort.value,
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

async function loadRelatedOptions() {
  if (!authStore.isAuthenticated) {
    return
  }
  relatedOptionsLoading.value = true
  relatedOptionsError.value = ''
  try {
    const [strategies, backtests, customBlocks, sharedBlocks, files] = await Promise.all([
      apiClient.get<{ items: StrategyOptionResponse[] }>('/strategies', {
        params: { page: 1, pageSize: 50 }
      }),
      apiClient.get<{ items: BacktestOptionResponse[] }>('/backtests', {
        params: { page: 1, pageSize: 50 }
      }),
      apiClient.get<{ items: CustomBlockOptionResponse[] }>('/custom-blocks', {
        params: { page: 1, pageSize: 50 }
      }),
      apiClient.get<{ items: SharedBlockOptionResponse[] }>('/shared-blocks', {
        params: { page: 1, pageSize: 50 }
      }),
      apiClient.get<{ items: UploadedFileOptionResponse[] }>('/files', {
        params: { page: 1, pageSize: 50 }
      })
    ])
    attachmentOptions.value = files.data.items
    relatedOptions.value = {
      strategy: strategies.data.items.map((item) => ({
        type: 'strategy',
        id: item.id,
        title: item.name,
        summary: `策略 · ${item.backtestConfig?.symbol || '未设置股票'} · ${formatTimeframe(
          item.backtestConfig?.timeframe
        )}`
      })),
      backtest: backtests.data.items.map((item) => ({
        type: 'backtest',
        id: item.id,
        title: `${item.symbol} ${formatTimeframe(item.timeframe)} 回测`,
        summary: `收益 ${item.totalReturnPercent}% · 最大回撤 ${item.maxDrawdownPercent}%`
      })),
      custom_block: customBlocks.data.items.map((item) => ({
        type: 'custom_block',
        id: item.id,
        title: item.name,
        summary: `我的积木 · ${item.category} · ${item.template?.nodes?.length ?? 0} 个积木`
      })),
      shared_block: sharedBlocks.data.items.map((item) => ({
        type: 'shared_block',
        id: item.id,
        title: item.name,
        summary: `公开积木 · ${item.category} · ${item.nodeCount} 个积木`
      }))
    }
  } catch {
    relatedOptionsError.value = '关联内容加载失败'
    attachmentOptionsError.value = '附件列表加载失败'
  } finally {
    relatedOptionsLoading.value = false
  }
}

async function searchPosts() {
  page.value = 1
  await loadPosts()
}

async function changeSort() {
  page.value = 1
  await loadPosts()
}

async function openPost(post: ForumPostItem, options: { syncUrl?: boolean } = {}) {
  detailLoading.value = true
  detailLoadingPostId.value = post.id
  error.value = ''
  try {
    const response = await apiClient.get<ForumPostDetail>(`/forum/posts/${post.id}`)
    selectedPost.value = response.data
    if (!posts.value.some((item) => item.id === response.data.id)) {
      posts.value = [response.data, ...posts.value]
    }
    commentContent.value = ''
    if (options.syncUrl ?? true) {
      void router.replace({ name: 'forum', query: { ...route.query, postId: String(post.id) } })
    }
  } catch {
    error.value = '帖子详情加载失败'
  } finally {
    detailLoading.value = false
    detailLoadingPostId.value = null
  }
}

async function togglePost(post: ForumPostItem) {
  if (selectedPost.value?.id === post.id && !detailLoading.value) {
    closePost()
    return
  }
  await openPost(post)
}

function closePost() {
  selectedPost.value = null
  commentContent.value = ''
  detailLoadingPostId.value = null
  const { postId, ...query } = route.query
  void postId
  void router.replace({ name: 'forum', query })
}

async function openPostFromRouteQuery() {
  const rawPostId = Array.isArray(route.query.postId) ? route.query.postId[0] : route.query.postId
  const postId = Number(rawPostId)
  if (!Number.isInteger(postId) || postId <= 0) {
    return
  }

  await openPost({ id: postId } as ForumPostItem, { syncUrl: false })
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
    sharedBlockId: null,
    attachmentFileIds: postAttachmentIds.value,
    ...relatedPostPayload()
  })
  postTitle.value = ''
  postContent.value = ''
  postTopic.value = ''
  relatedType.value = ''
  relatedId.value = ''
  postAttachmentIds.value = []
  status.value = '帖子已提交审核，可在个人空间-我的论坛查看进度'
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
  status.value = '评论已提交审核，可在个人空间-我的论坛查看进度'
}

async function togglePostReaction(post: ForumPostItem, reactionType: 'like' | 'favorite') {
  if (!authStore.isAuthenticated) {
    requireLogin()
    return
  }

  const isActive = reactionType === 'like' ? post.isLiked : post.isFavorited
  const endpoint = `/forum/posts/${post.id}/${reactionType}`
  error.value = ''
  try {
    if (isActive) {
      await apiClient.delete(endpoint)
      applyPostReactionState(post.id, reactionType, false)
      return
    }
    const response = await apiClient.post<ForumPostDetail>(endpoint)
    applyForumPostUpdate(response.data)
  } catch {
    error.value = reactionType === 'like' ? '点赞操作失败，请稍后重试' : '收藏操作失败，请稍后重试'
  }
}

function applyPostReactionState(
  postId: number,
  reactionType: 'like' | 'favorite',
  isActive: boolean
) {
  posts.value = posts.value.map((item) =>
    updatePostReactionState(item, postId, reactionType, isActive)
  )
  if (selectedPost.value?.id === postId) {
    selectedPost.value = updatePostReactionState(
      selectedPost.value,
      postId,
      reactionType,
      isActive
    ) as ForumPostDetail
  }
}

function updatePostReactionState(
  post: ForumPostItem,
  postId: number,
  reactionType: 'like' | 'favorite',
  isActive: boolean
): ForumPostItem {
  if (post.id !== postId) {
    return post
  }
  if (reactionType === 'like') {
    const likeCount = Math.max(0, post.likeCount + (isActive ? 1 : -1))
    return { ...post, isLiked: isActive, likeCount }
  }
  const favoriteCount = Math.max(0, post.favoriteCount + (isActive ? 1 : -1))
  return { ...post, isFavorited: isActive, favoriteCount }
}

function applyForumPostUpdate(updatedPost: ForumPostDetail) {
  posts.value = posts.value.map((item) => (item.id === updatedPost.id ? { ...item, ...updatedPost } : item))
  if (!posts.value.some((item) => item.id === updatedPost.id)) {
    posts.value = [updatedPost, ...posts.value]
  }
  if (selectedPost.value?.id === updatedPost.id) {
    selectedPost.value = updatedPost
  }
}

async function openRelatedContent() {
  const post = selectedPost.value
  if (!post?.relatedType || !post.relatedId) {
    return
  }

  error.value = ''
  try {
    if (post.relatedType === 'strategy') {
      const response = await apiClient.get<StrategyDetailResponse>(`/strategies/${post.relatedId}`)
      workspaceStore.openStrategy(response.data)
      void router.push('/')
      return
    }
    if (post.relatedType === 'custom_block') {
      const response = await apiClient.get<CustomBlockDetailResponse>(
        `/custom-blocks/${post.relatedId}`
      )
      workspaceStore.openCustomBlockTemplate({
        name: response.data.name,
        description: response.data.description,
        template: response.data.template
      })
      void router.push('/')
      return
    }
    if (post.relatedType === 'backtest') {
      void router.push({
        name: 'space',
        query: { tab: 'backtests', backtestId: String(post.relatedId) }
      })
      return
    }
    if (post.relatedType === 'shared_block') {
      void router.push({
        name: 'shared-blocks',
        query: { blockId: String(post.relatedId) }
      })
    }
  } catch {
    error.value = '关联内容打开失败，请确认你有权限访问'
  }
}

async function downloadAttachment(attachment: ForumAttachment) {
  error.value = ''
  try {
    const endpoint = attachment.downloadUrl.startsWith('/api')
      ? attachment.downloadUrl.slice('/api'.length)
      : attachment.downloadUrl
    const response = await apiClient.get<Blob>(endpoint, {
      responseType: 'blob'
    })
    const blob = response.data instanceof Blob
      ? response.data
      : new Blob([response.data], { type: attachment.contentType })
    const objectUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = objectUrl
    link.download = attachment.originalName
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(objectUrl)
  } catch {
    error.value = '附件下载失败，请稍后重试'
  }
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

function formatFileSize(size: number) {
  if (size < 1024) {
    return `${size} B`
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1).replace(/\.0$/, '')} KB`
  }
  return `${(size / 1024 / 1024).toFixed(1).replace(/\.0$/, '')} MB`
}

function formatTimeframe(value: string | undefined) {
  if (value === '1m') {
    return '1分钟'
  }
  if (value === '5m') {
    return '5分钟'
  }
  return '未设置周期'
}

function formatRelatedType(value: ForumRelatedType | null) {
  if (value === 'strategy') {
    return '策略'
  }
  if (value === 'backtest') {
    return '回测'
  }
  if (value === 'custom_block') {
    return '我的积木'
  }
  if (value === 'shared_block') {
    return '公开积木'
  }
  return '关联内容'
}

function relatedPostPayload() {
  if (relatedType.value === '' || relatedId.value === '') {
    return {}
  }
  return {
    relatedType: relatedType.value,
    relatedId: Number(relatedId.value)
  }
}

onMounted(() => {
  void (async () => {
    await Promise.all([loadPosts(), loadRelatedOptions()])
    await openPostFromRouteQuery()
  })()
})

watch(
  () => authStore.isAuthenticated,
  (isAuthenticated, wasAuthenticated) => {
    if (isAuthenticated && !wasAuthenticated) {
      void loadRelatedOptions()
    }
  }
)
</script>

<template>
  <section class="forum-page">
    <header class="forum-header">
      <div>
        <h1>论坛</h1>
        <p>分享交易策略、回测结果和积木使用经验。帖子与评论提交后会进入审核。</p>
      </div>
      <form class="forum-search" @submit.prevent="searchPosts">
        <label class="forum-sort-control">
          <span>排序</span>
          <select v-model="sort" class="forum-sort-select" @change="changeSort">
            <option value="latest_reply">最新回复</option>
            <option value="newest">最新发布</option>
            <option value="most_commented">最多评论</option>
          </select>
        </label>
        <input v-model="keyword" class="forum-search-input" placeholder="搜索帖子" />
        <input v-model="topicFilter" class="forum-topic-filter-input" placeholder="分类/标签" />
        <input v-model="authorFilter" class="forum-author-filter-input" placeholder="作者" />
        <select v-model="relatedTypeFilter" class="forum-related-filter-select">
          <option value="">全部关联</option>
          <option value="strategy">策略</option>
          <option value="backtest">回测</option>
          <option value="custom_block">我的积木</option>
          <option value="shared_block">公开积木</option>
        </select>
        <button class="forum-search-button" type="button" @click="searchPosts">搜索</button>
      </form>
    </header>

    <section class="forum-composer">
      <div>
        <strong>发布新帖</strong>
        <p>写下策略思路、回测结论或积木组合方法。</p>
      </div>
      <input v-model="postTitle" class="forum-post-title-input" placeholder="帖子标题" />
      <input
        v-model="postTopic"
        class="forum-post-topic-input"
        placeholder="帖子分类，例如：策略复盘、回测问题、积木组合"
      />
      <div class="forum-related-picker">
        <select
          v-model="relatedType"
          class="forum-related-type-select"
          :disabled="!authStore.isAuthenticated || relatedOptionsLoading"
          @change="relatedId = ''"
        >
          <option value="">不关联内容</option>
          <option value="strategy">我的策略</option>
          <option value="backtest">我的回测</option>
          <option value="custom_block">我的积木</option>
          <option value="shared_block">公开积木</option>
        </select>
        <select
          v-model="relatedId"
          class="forum-related-id-select"
          :disabled="relatedType === '' || selectedRelatedOptions.length === 0"
        >
          <option value="">
            {{ relatedType === '' ? '先选择类型' : '选择要关联的内容' }}
          </option>
          <option v-for="option in selectedRelatedOptions" :key="option.id" :value="String(option.id)">
            {{ option.title }}
          </option>
        </select>
        <small v-if="relatedOptionsError">{{ relatedOptionsError }}</small>
      </div>
      <div v-if="authStore.isAuthenticated" class="forum-attachment-picker">
        <strong>附件</strong>
        <div v-if="attachmentOptions.length > 0" class="forum-attachment-options">
          <label
            v-for="file in attachmentOptions"
            :key="file.id"
            class="forum-attachment-option"
          >
            <input v-model="postAttachmentIds" type="checkbox" :value="file.id" />
            <span>{{ file.originalName }}</span>
            <small>{{ formatFileSize(file.size) }}</small>
          </label>
        </div>
        <small v-else-if="attachmentOptionsError">{{ attachmentOptionsError }}</small>
        <small v-else>暂无可选附件</small>
      </div>
      <textarea
        v-model="postContent"
        class="forum-post-content-input"
        placeholder="正文内容"
      ></textarea>
      <button class="forum-post-submit-button" type="button" @click="submitPost">提交审核</button>
    </section>

    <p v-if="error" class="form-error">{{ error }}</p>
    <p v-if="status" class="space-muted">{{ status }}</p>

    <section class="forum-post-list">
      <p v-if="loading" class="space-muted">正在加载帖子</p>
      <p v-else-if="posts.length === 0" class="space-muted">暂无公开帖子</p>
      <article
        v-for="post in posts"
        v-else
        :key="post.id"
        class="forum-post-item"
        :class="{ 'is-expanded': selectedPost?.id === post.id }"
      >
        <div class="forum-post-topic">{{ post.topic }}</div>
        <div>
          <h2>{{ post.title }}</h2>
          <p>{{ post.content }}</p>
          <div v-if="post.relatedTitle" class="forum-related-chip">
            {{ formatRelatedType(post.relatedType) }} · {{ post.relatedTitle }}
          </div>
          <div v-if="post.attachments?.length" class="forum-related-chip">
            附件 {{ post.attachments.length }}
          </div>
          <small>
            作者 {{ post.authorName }} · 评论 {{ post.commentCount }} ·
            {{ formatDate(post.updatedAt) }}
          </small>
        </div>
        <div class="forum-post-actions">
          <button
            class="forum-post-like-button"
            type="button"
            :class="{ 'is-active': post.isLiked }"
            @click="togglePostReaction(post, 'like')"
          >
            {{ post.isLiked ? '已赞' : '点赞' }} {{ post.likeCount }}
          </button>
          <button
            class="forum-post-favorite-button"
            type="button"
            :class="{ 'is-active': post.isFavorited }"
            @click="togglePostReaction(post, 'favorite')"
          >
            {{ post.isFavorited ? '已收藏' : '收藏' }} {{ post.favoriteCount }}
          </button>
          <button class="forum-post-detail-button" type="button" @click="togglePost(post)">
            {{ selectedPost?.id === post.id ? '收起' : '查看' }}
          </button>
        </div>

        <div v-if="detailLoading && detailLoadingPostId === post.id" class="forum-inline-thread-panel">
          <p class="space-muted">正在加载帖子详情</p>
        </div>
        <div
          v-else-if="selectedPost?.id === post.id"
          class="forum-inline-thread-panel"
        >
          <div class="forum-thread-main">
            <button class="forum-thread-close-button" type="button" @click="closePost">
              收起
            </button>
            <span>{{ selectedPost.topic }}</span>
            <h2>{{ selectedPost.title }}</h2>
            <p>{{ selectedPost.content }}</p>
            <section v-if="selectedPost.relatedTitle" class="forum-related-card">
              <small>关联内容 · {{ formatRelatedType(selectedPost.relatedType) }}</small>
              <strong>{{ selectedPost.relatedTitle }}</strong>
              <p>{{ selectedPost.relatedSummary }}</p>
              <button class="forum-related-open-button" type="button" @click="openRelatedContent">
                打开关联内容
              </button>
            </section>
            <section v-if="selectedPost.attachments.length" class="forum-attachment-card">
              <strong>附件</strong>
              <button
                v-for="attachment in selectedPost.attachments"
                :key="attachment.id"
                class="forum-attachment-download-button"
                type="button"
                @click="downloadAttachment(attachment)"
              >
                <span>{{ attachment.originalName }}</span>
                <small>{{ formatFileSize(attachment.size) }}</small>
              </button>
            </section>
            <small>
              作者 {{ selectedPost.authorName }} · 点赞 {{ selectedPost.likeCount }} · 收藏
              {{ selectedPost.favoriteCount }} · {{ formatDate(selectedPost.updatedAt) }}
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
        </div>
      </article>

      <footer class="space-footer">
        <span>共 {{ total }} 个公开帖子</span>
        <div class="space-pagination">
          <button
            type="button"
            data-pagination="forum-prev"
            :disabled="page <= 1"
            @click="changePage(page - 1)"
          >
            上一页
          </button>
          <span>第 {{ page }} / {{ totalPages }} 页 · 每页 {{ pageSize }} 条</span>
          <button
            type="button"
            data-pagination="forum-next"
            :disabled="page >= totalPages"
            @click="changePage(page + 1)"
          >
            下一页
          </button>
        </div>
      </footer>
    </section>
  </section>
</template>
