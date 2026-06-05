<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { apiClient } from '../api/http'
import {
  useStrategyWorkspaceStore,
  type SavedStrategy
} from '../stores/strategyWorkspace'

interface StrategyListResponse {
  items: SavedStrategy[]
  total: number
  page: number
  pageSize: number
}

const router = useRouter()
const workspaceStore = useStrategyWorkspaceStore()
const strategies = ref<SavedStrategy[]>([])
const keyword = ref('')
const page = ref(1)
const pageSize = 10
const total = ref(0)
const loading = ref(false)
const error = ref('')

async function loadStrategies() {
  loading.value = true
  error.value = ''
  try {
    const response = await apiClient.get<StrategyListResponse>('/strategies', {
      params: {
        keyword: keyword.value.trim(),
        page: page.value,
        pageSize
      }
    })
    strategies.value = response.data.items
    total.value = response.data.total
  } catch {
    error.value = '策略列表加载失败，请确认已登录'
  } finally {
    loading.value = false
  }
}

async function searchStrategies() {
  page.value = 1
  await loadStrategies()
}

function openStrategy(strategy: SavedStrategy) {
  workspaceStore.openStrategy(strategy)
  void router.push('/')
}

async function deleteStrategy(strategy: SavedStrategy) {
  await apiClient.delete(`/strategies/${strategy.id}`)
  await loadStrategies()
}

onMounted(() => {
  void loadStrategies()
})
</script>

<template>
  <section class="page-panel personal-space">
    <header class="space-header">
      <div>
        <h1>个人空间</h1>
        <p>管理已保存的策略，并重新打开到搭建画布继续编辑。</p>
      </div>
      <form class="space-search" @submit.prevent="searchStrategies">
        <input v-model="keyword" placeholder="搜索策略" />
        <button type="submit">搜索</button>
      </form>
    </header>

    <p v-if="error" class="form-error">{{ error }}</p>
    <p v-else-if="loading" class="space-muted">正在加载策略</p>
    <p v-else-if="strategies.length === 0" class="space-muted">暂无已保存策略</p>

    <div v-else class="strategy-list">
      <article v-for="strategy in strategies" :key="strategy.id" class="strategy-item">
        <div>
          <h2>{{ strategy.name }}</h2>
          <p>{{ strategy.description || '无描述' }}</p>
          <small>
            {{ strategy.backtestConfig?.symbol || '未设置股票' }}
            ·
            {{ strategy.backtestConfig?.timeframe === '1m' ? '1分钟' : '5分钟' }}
            ·
            更新于 {{ strategy.updatedAt.slice(0, 10) }}
          </small>
        </div>
        <div class="strategy-item-actions">
          <button class="strategy-open-button" type="button" @click="openStrategy(strategy)">
            打开
          </button>
          <button class="strategy-delete-button" type="button" @click="deleteStrategy(strategy)">
            删除
          </button>
        </div>
      </article>
    </div>

    <footer class="space-footer">
      <span>共 {{ total }} 条策略</span>
    </footer>
  </section>
</template>
