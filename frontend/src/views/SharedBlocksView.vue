<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { apiClient } from '../api/http'
import { useAuthStore } from '../stores/auth'

interface SharedBlockTemplateNode {
  id: string
  type: string
  label: string
  x: number
  y: number
  params: Record<string, string>
}

interface SharedBlockTemplate {
  version: number
  nodes: SharedBlockTemplateNode[]
  edges: Array<{ id: string; from: string; to: string }>
  viewport: { x: number; y: number; scale: number }
}

interface SharedBlockItem {
  id: number
  ownerId: number
  authorName: string
  name: string
  description: string | null
  category: string
  tags: string[]
  reviewStatus: 'approved' | 'pending_review' | 'rejected' | 'private'
  nodeCount: number
  connectionCount: number
  viewCount: number
  favoriteCount: number
  importCount: number
  isFavorited: boolean
  createdAt: string
  updatedAt: string
}

interface SharedBlockDetail extends SharedBlockItem {
  template: SharedBlockTemplate
}

interface SharedBlockListResponse {
  items: SharedBlockItem[]
  total: number
  page: number
  pageSize: number
}

interface ImportedBlockResponse {
  id: number
  name: string
}

const authStore = useAuthStore()
const activeMode = ref<'browse' | 'review'>('browse')
const sharedBlocks = ref<SharedBlockItem[]>([])
const reviewItems = ref<SharedBlockItem[]>([])
const selectedBlock = ref<SharedBlockDetail | null>(null)
const expandedBlockId = ref<number | null>(null)
const keyword = ref('')
const category = ref('')
const tag = ref('')
const sort = ref('latest')
const reviewKeyword = ref('')
const page = ref(1)
const reviewPage = ref(1)
const pageSize = 10
const total = ref(0)
const reviewTotal = ref(0)
const loading = ref(false)
const reviewLoading = ref(false)
const detailLoadingBlockId = ref<number | null>(null)
const error = ref('')
const status = ref('')

const isAdmin = computed(() => authStore.user?.roles.includes('admin') ?? false)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const reviewTotalPages = computed(() => Math.max(1, Math.ceil(reviewTotal.value / pageSize)))

function requireLogin() {
  window.dispatchEvent(new CustomEvent('sts:auth-required'))
}

function isUnauthorizedError(error: unknown) {
  return (
    typeof error === 'object' &&
    error !== null &&
    'response' in error &&
    (error as { response?: { status?: number } }).response?.status === 401
  )
}

async function fetchSharedBlockList() {
  const response = await apiClient.get<SharedBlockListResponse>('/shared-blocks', {
    params: {
      keyword: keyword.value.trim(),
      category: category.value.trim(),
      tag: tag.value.trim(),
      sort: sort.value,
      page: page.value,
      pageSize
    }
  })
  sharedBlocks.value = response.data.items
  total.value = response.data.total
  if (
    selectedBlock.value &&
    !response.data.items.some((block) => block.id === selectedBlock.value?.id)
  ) {
    selectedBlock.value = null
    expandedBlockId.value = null
    detailLoadingBlockId.value = null
  }
}

async function loadSharedBlocks() {
  loading.value = true
  error.value = ''
  try {
    await fetchSharedBlockList()
  } catch (requestError) {
    if (isUnauthorizedError(requestError) && authStore.isAuthenticated) {
      authStore.logout()
      try {
        await fetchSharedBlockList()
        status.value = '登录状态已失效，已按游客身份加载公开积木'
        return
      } catch {
        error.value = '公开积木加载失败'
        return
      }
    }
    error.value = '公开积木加载失败'
  } finally {
    loading.value = false
  }
}

async function loadReviewItems() {
  reviewLoading.value = true
  error.value = ''
  try {
    const response = await apiClient.get<SharedBlockListResponse>('/admin/custom-block-reviews', {
      params: {
        keyword: reviewKeyword.value.trim(),
        page: reviewPage.value,
        pageSize
      }
    })
    reviewItems.value = response.data.items
    reviewTotal.value = response.data.total
  } catch {
    error.value = '审核列表加载失败'
  } finally {
    reviewLoading.value = false
  }
}

async function openBrowseMode() {
  activeMode.value = 'browse'
}

async function openReviewMode() {
  activeMode.value = 'review'
  await loadReviewItems()
}

async function searchReviewItems() {
  reviewPage.value = 1
  await loadReviewItems()
}

async function toggleDetail(block: SharedBlockItem) {
  if (expandedBlockId.value === block.id) {
    expandedBlockId.value = null
    selectedBlock.value = null
    detailLoadingBlockId.value = null
    return
  }

  expandedBlockId.value = block.id
  detailLoadingBlockId.value = block.id
  error.value = ''
  try {
    const response = await apiClient.get<SharedBlockDetail>(`/shared-blocks/${block.id}`)
    selectedBlock.value = response.data
    syncSharedBlock(response.data)
  } catch {
    expandedBlockId.value = null
    error.value = '公开积木详情加载失败'
  } finally {
    if (detailLoadingBlockId.value === block.id) {
      detailLoadingBlockId.value = null
    }
  }
}

async function toggleFavorite(block: SharedBlockItem) {
  if (!authStore.isAuthenticated) {
    requireLogin()
    return
  }

  status.value = ''
  if (block.isFavorited) {
    await apiClient.delete(`/shared-blocks/${block.id}/favorite`)
    block.isFavorited = false
    block.favoriteCount = Math.max(0, block.favoriteCount - 1)
    syncSelectedBlock(block)
    status.value = '已取消收藏'
    return
  }

  const response = await apiClient.post<SharedBlockDetail>(`/shared-blocks/${block.id}/favorite`)
  block.isFavorited = true
  block.favoriteCount = response.data.favoriteCount
  syncSelectedBlock(response.data)
  status.value = '已收藏'
}

async function importBlock(block: SharedBlockItem) {
  if (!authStore.isAuthenticated) {
    requireLogin()
    return
  }

  const response = await apiClient.post<ImportedBlockResponse>(`/shared-blocks/${block.id}/import`)
  block.importCount += 1
  syncSelectedBlock(block)
  status.value = `已导入到我的积木：${response.data.name}`
}

async function approveReview(block: SharedBlockItem) {
  await apiClient.post(`/admin/custom-block-reviews/${block.id}/approve`)
  status.value = '审核已通过'
  await loadReviewItems()
  await loadSharedBlocks()
}

async function rejectReview(block: SharedBlockItem) {
  await apiClient.post(`/admin/custom-block-reviews/${block.id}/reject`)
  status.value = '审核已拒绝'
  await loadReviewItems()
}

async function changePage(nextPage: number) {
  if (nextPage < 1 || nextPage > totalPages.value || nextPage === page.value) {
    return
  }
  page.value = nextPage
  await loadSharedBlocks()
}

async function changeReviewPage(nextPage: number) {
  if (
    nextPage < 1 ||
    nextPage > reviewTotalPages.value ||
    nextPage === reviewPage.value
  ) {
    return
  }
  reviewPage.value = nextPage
  await loadReviewItems()
}

function syncSharedBlock(block: SharedBlockItem) {
  const index = sharedBlocks.value.findIndex((item) => item.id === block.id)
  if (index >= 0) {
    sharedBlocks.value[index] = { ...sharedBlocks.value[index], ...block }
  }
}

function syncSelectedBlock(block: SharedBlockItem) {
  syncSharedBlock(block)
  if (selectedBlock.value?.id === block.id) {
    selectedBlock.value = { ...selectedBlock.value, ...block }
  }
}

function formatDate(value: string) {
  return value.slice(0, 10)
}

function isPreviewOpen(block: SharedBlockItem) {
  return expandedBlockId.value === block.id
}

function isPreviewLoading(block: SharedBlockItem) {
  return detailLoadingBlockId.value === block.id
}

function getPreviewBounds(template: SharedBlockTemplate) {
  const nodes = template.nodes
  if (nodes.length === 0) {
    return { minX: 0, minY: 0, width: 1, height: 1 }
  }

  const xs = nodes.map((node) => node.x)
  const ys = nodes.map((node) => node.y)
  const minX = Math.min(...xs)
  const minY = Math.min(...ys)
  const maxX = Math.max(...xs)
  const maxY = Math.max(...ys)
  return {
    minX,
    minY,
    width: Math.max(maxX - minX, 1),
    height: Math.max(maxY - minY, 1)
  }
}

function getPreviewPoint(node: SharedBlockTemplateNode, template: SharedBlockTemplate) {
  const bounds = getPreviewBounds(template)
  return {
    x: 12 + ((node.x - bounds.minX) / bounds.width) * 76,
    y: 18 + ((node.y - bounds.minY) / bounds.height) * 64
  }
}

function getPreviewNodes(template: SharedBlockTemplate) {
  return template.nodes.map((node) => {
    const point = getPreviewPoint(node, template)
    return {
      id: node.id,
      label: node.label || node.type,
      type: node.type,
      style: {
        left: `${point.x}%`,
        top: `${point.y}%`
      }
    }
  })
}

function getPreviewEdges(template: SharedBlockTemplate) {
  return template.edges.flatMap((edge) => {
    const fromNode = template.nodes.find((node) => node.id === edge.from)
    const toNode = template.nodes.find((node) => node.id === edge.to)
    if (!fromNode || !toNode) {
      return []
    }

    const fromPoint = getPreviewPoint(fromNode, template)
    const toPoint = getPreviewPoint(toNode, template)
    return [
      {
        id: edge.id,
        x1: `${fromPoint.x}%`,
        y1: `${fromPoint.y}%`,
        x2: `${toPoint.x}%`,
        y2: `${toPoint.y}%`
      }
    ]
  })
}

function handleSharedBlockSearch(event: Event) {
  const detail = (event as CustomEvent<{ keyword?: string }>).detail
  keyword.value = detail?.keyword ?? ''
  page.value = 1
  activeMode.value = 'browse'
  void loadSharedBlocks()
}

onMounted(() => {
  window.addEventListener('sts:shared-block-search', handleSharedBlockSearch)
  void loadSharedBlocks()
})

onBeforeUnmount(() => {
  window.removeEventListener('sts:shared-block-search', handleSharedBlockSearch)
})
</script>

<template>
  <section class="shared-blocks">
    <section class="shared-block-hero">
      <div class="shared-block-hero-art" aria-hidden="true">
        <span class="shared-block-hero-grid"></span>
        <span class="shared-block-candle candle-one"></span>
        <span class="shared-block-candle candle-two"></span>
        <span class="shared-block-candle candle-three"></span>
        <span class="shared-block-candle candle-four"></span>
        <span class="shared-block-signal signal-one"></span>
        <span class="shared-block-signal signal-two"></span>
        <span class="shared-block-flow flow-one"></span>
        <span class="shared-block-flow flow-two"></span>
      </div>
      <div class="shared-block-hero-copy">
        <span>STS 积木市场</span>
        <h1>创建你的交易策略</h1>
        <p>从公开积木中挑选成熟的买卖、风控和信号逻辑，导入后继续在画布上拼接成自己的盘中策略。</p>
        <a class="shared-block-start-button" href="/">开始搭建</a>
      </div>
    </section>

    <header class="shared-block-market-header">
      <div>
        <h2>
          {{ activeMode === 'browse' ? '公开积木精选' : '待审核积木' }}
          <span v-if="activeMode === 'browse'">复制常用交易逻辑</span>
        </h2>
        <p>
          {{
            activeMode === 'browse'
              ? '在上方导航栏搜索你需要的条件、风控或信号积木。'
              : '管理员可以在这里审核用户提交的公开积木。'
          }}
        </p>
      </div>
      <div class="shared-block-mode-tabs">
        <button
          class="shared-block-browse-tab"
          type="button"
          :class="{ 'is-active': activeMode === 'browse' }"
          @click="openBrowseMode"
        >
          公开积木
        </button>
        <button
          v-if="isAdmin"
          class="shared-block-review-tab"
          type="button"
          :class="{ 'is-active': activeMode === 'review' }"
          @click="openReviewMode"
        >
          审核
        </button>
      </div>
    </header>

    <p v-if="error" class="form-error">{{ error }}</p>
    <p v-if="status" class="space-muted">{{ status }}</p>

    <div v-if="activeMode === 'browse'" class="shared-block-layout">
      <div class="shared-block-marketplace">
        <p v-if="loading" class="space-muted">正在加载公开积木</p>
        <p v-else-if="sharedBlocks.length === 0" class="space-muted">暂无公开积木</p>
        <div v-else class="shared-block-list">
          <article v-for="block in sharedBlocks" :key="block.id" class="shared-block-card">
            <div class="shared-block-card-topline">
              <span>{{ block.category }}</span>
              <small>{{ formatDate(block.updatedAt) }}</small>
            </div>
            <h2>{{ block.name }}</h2>
            <p>{{ block.description || '无描述' }}</p>
            <small>
              作者 {{ block.authorName }} · {{ block.nodeCount }} 个积木 ·
              {{ block.connectionCount }} 条连接
            </small>
            <div class="shared-block-tags">
              <span v-for="blockTag in block.tags" :key="blockTag">{{ blockTag }}</span>
            </div>
            <div class="shared-block-metrics">
              <span>浏览 {{ block.viewCount }}</span>
              <span>收藏 {{ block.favoriteCount }}</span>
              <span>导入 {{ block.importCount }}</span>
            </div>
            <div class="shared-block-card-footer">
              <strong>免费导入</strong>
              <span>{{ block.importCount }} 次导入</span>
            </div>
            <div class="shared-block-actions">
              <button class="shared-block-detail-button" type="button" @click="toggleDetail(block)">
                {{ isPreviewOpen(block) ? '收起' : '查看' }}
              </button>
              <button class="shared-block-favorite-button" type="button" @click="toggleFavorite(block)">
                {{ block.isFavorited ? '已收藏' : '收藏' }}
              </button>
              <button class="shared-block-import-button" type="button" @click="importBlock(block)">
                导入
              </button>
            </div>
            <div v-if="isPreviewOpen(block)" class="shared-block-inline-preview">
              <p v-if="isPreviewLoading(block)" class="space-muted">正在加载概览</p>
              <template v-else-if="selectedBlock && selectedBlock.id === block.id">
                <div class="shared-block-preview-header">
                  <strong>积木画布概览</strong>
                  <small>
                    {{ selectedBlock.template.nodes.length }} 个积木 ·
                    {{ selectedBlock.template.edges.length }} 条连接
                  </small>
                </div>
                <div class="shared-block-preview-canvas" aria-label="积木画布概览">
                  <svg class="shared-block-preview-lines" aria-hidden="true">
                    <line
                      v-for="edge in getPreviewEdges(selectedBlock.template)"
                      :key="edge.id"
                      class="shared-block-preview-edge"
                      :x1="edge.x1"
                      :y1="edge.y1"
                      :x2="edge.x2"
                      :y2="edge.y2"
                    />
                  </svg>
                  <span
                    v-for="node in getPreviewNodes(selectedBlock.template)"
                    :key="node.id"
                    class="shared-block-preview-node"
                    :style="node.style"
                  >
                    <b>{{ node.label }}</b>
                    <small>{{ node.type }}</small>
                  </span>
                </div>
              </template>
            </div>
          </article>
        </div>

        <footer class="space-footer">
          <span>共 {{ total }} 个公开积木</span>
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
      </div>
    </div>

    <div v-else class="shared-block-review-panel">
      <form class="shared-block-toolbar" @submit.prevent="searchReviewItems">
        <input
          v-model="reviewKeyword"
          class="shared-block-review-search-input"
          placeholder="搜索待审核积木"
        />
        <button class="shared-block-review-search-button" type="button" @click="searchReviewItems">
          搜索
        </button>
      </form>

      <div class="shared-block-list">
        <p v-if="reviewLoading" class="space-muted">正在加载待审核积木</p>
        <p v-else-if="reviewItems.length === 0" class="space-muted">暂无待审核积木</p>
        <article v-for="block in reviewItems" v-else :key="block.id" class="shared-block-card">
          <div class="shared-block-card-header">
            <div>
              <h2>{{ block.name }}</h2>
              <p>{{ block.description || '无描述' }}</p>
            </div>
            <strong>{{ block.category }}</strong>
          </div>
          <small>
            作者 {{ block.authorName }} · {{ block.nodeCount }} 个积木 ·
            {{ block.connectionCount }} 条连接 · 提交于 {{ formatDate(block.updatedAt) }}
          </small>
          <div class="shared-block-tags">
            <span v-for="blockTag in block.tags" :key="blockTag">{{ blockTag }}</span>
          </div>
          <div class="shared-block-actions">
            <button class="shared-block-approve-button" type="button" @click="approveReview(block)">
              通过
            </button>
            <button class="shared-block-reject-button" type="button" @click="rejectReview(block)">
              拒绝
            </button>
          </div>
        </article>
      </div>

      <footer class="space-footer">
        <span>共 {{ reviewTotal }} 个待审核积木</span>
        <div class="space-pagination">
          <button
            type="button"
            :disabled="reviewPage <= 1"
            @click="changeReviewPage(reviewPage - 1)"
          >
            上一页
          </button>
          <span>第 {{ reviewPage }} / {{ reviewTotalPages }} 页</span>
          <button
            type="button"
            :disabled="reviewPage >= reviewTotalPages"
            @click="changeReviewPage(reviewPage + 1)"
          >
            下一页
          </button>
        </div>
      </footer>
    </div>
  </section>
</template>
