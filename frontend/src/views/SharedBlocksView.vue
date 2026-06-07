<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
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
  reviewStatus: 'approved'
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

interface BlockSummary {
  label: string
  count: number
}

const authStore = useAuthStore()
const sharedBlocks = ref<SharedBlockItem[]>([])
const selectedBlock = ref<SharedBlockDetail | null>(null)
const keyword = ref('')
const category = ref('')
const tag = ref('')
const sort = ref('latest')
const page = ref(1)
const pageSize = 10
const total = ref(0)
const loading = ref(false)
const detailLoading = ref(false)
const error = ref('')
const status = ref('')

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

function requireLogin() {
  window.dispatchEvent(new CustomEvent('sts:auth-required'))
}

async function loadSharedBlocks() {
  loading.value = true
  error.value = ''
  try {
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
    }
  } catch {
    error.value = '公开积木加载失败'
  } finally {
    loading.value = false
  }
}

async function searchSharedBlocks() {
  page.value = 1
  await loadSharedBlocks()
}

async function openDetail(block: SharedBlockItem) {
  detailLoading.value = true
  error.value = ''
  try {
    const response = await apiClient.get<SharedBlockDetail>(`/shared-blocks/${block.id}`)
    selectedBlock.value = response.data
    syncSharedBlock(response.data)
  } catch {
    error.value = '公开积木详情加载失败'
  } finally {
    detailLoading.value = false
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

async function changePage(nextPage: number) {
  if (nextPage < 1 || nextPage > totalPages.value || nextPage === page.value) {
    return
  }
  page.value = nextPage
  await loadSharedBlocks()
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

function summarizeNodes(template: SharedBlockTemplate | null | undefined) {
  const nodes = template?.nodes ?? []
  const summary = nodes.reduce<Map<string, BlockSummary>>((groups, node) => {
    const label = node.label || node.type
    const current = groups.get(label) ?? { label, count: 0 }
    current.count += 1
    groups.set(label, current)
    return groups
  }, new Map())
  return Array.from(summary.values()).sort((left, right) => left.label.localeCompare(right.label))
}

function formatDate(value: string) {
  return value.slice(0, 10)
}

onMounted(() => {
  void loadSharedBlocks()
})
</script>

<template>
  <section class="shared-blocks">
    <div class="space-section-header">
      <div>
        <h1>积木分享</h1>
        <p>搜索公开积木，查看结构后收藏或导入到自己的积木库。</p>
      </div>
    </div>

    <form class="shared-block-toolbar" @submit.prevent="searchSharedBlocks">
      <input
        v-model="keyword"
        class="shared-block-search-input"
        placeholder="搜索名称、分类或标签"
      />
      <input v-model="category" class="shared-block-category-input" placeholder="分类" />
      <input v-model="tag" class="shared-block-tag-input" placeholder="标签" />
      <select v-model="sort" class="shared-block-sort-select">
        <option value="latest">最新</option>
        <option value="popular">热门</option>
        <option value="beginner">新手友好</option>
      </select>
      <button class="shared-block-search-button" type="button" @click="searchSharedBlocks">
        搜索
      </button>
    </form>

    <p v-if="error" class="form-error">{{ error }}</p>
    <p v-if="status" class="space-muted">{{ status }}</p>

    <div class="shared-block-layout">
      <div class="shared-block-list">
        <p v-if="loading" class="space-muted">正在加载公开积木</p>
        <p v-else-if="sharedBlocks.length === 0" class="space-muted">暂无公开积木</p>
        <article v-for="block in sharedBlocks" v-else :key="block.id" class="shared-block-card">
          <div class="shared-block-card-header">
            <div>
              <h2>{{ block.name }}</h2>
              <p>{{ block.description || '无描述' }}</p>
            </div>
            <strong>{{ block.category }}</strong>
          </div>
          <small>
            作者 {{ block.authorName }} · {{ block.nodeCount }} 个积木 ·
            {{ block.connectionCount }} 条连接 · 更新于 {{ formatDate(block.updatedAt) }}
          </small>
          <div class="shared-block-tags">
            <span v-for="blockTag in block.tags" :key="blockTag">{{ blockTag }}</span>
          </div>
          <div class="shared-block-metrics">
            <span>浏览 {{ block.viewCount }}</span>
            <span>收藏 {{ block.favoriteCount }}</span>
            <span>导入 {{ block.importCount }}</span>
          </div>
          <div class="shared-block-actions">
            <button class="shared-block-detail-button" type="button" @click="openDetail(block)">
              查看
            </button>
            <button class="shared-block-favorite-button" type="button" @click="toggleFavorite(block)">
              {{ block.isFavorited ? '已收藏' : '收藏' }}
            </button>
            <button class="shared-block-import-button" type="button" @click="importBlock(block)">
              导入
            </button>
          </div>
        </article>

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

      <aside class="shared-block-detail">
        <p v-if="detailLoading" class="space-muted">正在加载详情</p>
        <template v-else-if="selectedBlock">
          <h2>{{ selectedBlock.name }}</h2>
          <p>{{ selectedBlock.description || '无描述' }}</p>
          <small>
            作者 {{ selectedBlock.authorName }} · 浏览 {{ selectedBlock.viewCount }} · 收藏
            {{ selectedBlock.favoriteCount }} · 导入 {{ selectedBlock.importCount }}
          </small>
          <div class="shared-block-tags">
            <span v-for="blockTag in selectedBlock.tags" :key="blockTag">{{ blockTag }}</span>
          </div>
          <div class="shared-block-node-summary">
            <span v-for="summary in summarizeNodes(selectedBlock.template)" :key="summary.label">
              {{ summary.label }} x{{ summary.count }}
            </span>
          </div>
          <div class="shared-block-actions">
            <button
              class="shared-block-favorite-button"
              type="button"
              @click="toggleFavorite(selectedBlock)"
            >
              {{ selectedBlock.isFavorited ? '已收藏' : '收藏' }}
            </button>
            <button
              class="shared-block-import-button"
              type="button"
              @click="importBlock(selectedBlock)"
            >
              导入
            </button>
          </div>
        </template>
        <p v-else class="space-muted">选择一个公开积木查看结构。</p>
      </aside>
    </div>
  </section>
</template>
