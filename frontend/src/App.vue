<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import AuthModal from './components/AuthModal.vue'
import { useAuthStore } from './stores/auth'

type AuthMode = 'login' | 'register'

const authStore = useAuthStore()
const route = useRoute()
const isAuthModalOpen = ref(false)
const authModalMode = ref<AuthMode>('login')

const routeSectionTitles: Record<string, string> = {
  builder: '策略工作台',
  space: '个人空间',
  forum: '论坛',
  'shared-blocks': '积木分享',
  'admin-review': '审核管理',
  login: '登录',
  register: '注册'
}

const routeName = computed(() => (typeof route.name === 'string' ? route.name : ''))
const isBuilderRoute = computed(() => routeName.value === 'builder' || route.path === '/')
const isSharedBlocksRoute = computed(() => routeName.value === 'shared-blocks')
const isAdmin = computed(() => authStore.user?.roles.includes('admin') ?? false)
const currentSectionTitle = computed(
  () => routeSectionTitles[routeName.value] ?? (isBuilderRoute.value ? '策略工作台' : 'STS')
)
const sharedBlockTopSearch = ref('')

const displayedUsername = computed(() => {
  const username = authStore.user?.username ?? ''
  return username.length > 6 ? username.slice(-6) : username
})

function dispatchBuilderAction(action: 'save' | 'backtest' | 'publish') {
  window.dispatchEvent(new CustomEvent('sts:builder-action', { detail: { action } }))
}

function submitSharedBlockTopSearch() {
  window.dispatchEvent(
    new CustomEvent('sts:shared-block-search', {
      detail: { keyword: sharedBlockTopSearch.value }
    })
  )
}

function openAuthModal(mode: AuthMode = 'login') {
  authModalMode.value = mode
  isAuthModalOpen.value = true
}

function handleAuthRequired() {
  openAuthModal('login')
}

onMounted(() => {
  window.addEventListener('sts:auth-required', handleAuthRequired)
})

onBeforeUnmount(() => {
  window.removeEventListener('sts:auth-required', handleAuthRequired)
})
</script>

<template>
  <div class="app-shell">
    <aside class="side-nav" aria-label="主导航">
      <div class="brand">STS</div>
      <RouterLink to="/">搭建</RouterLink>
      <RouterLink to="/space">空间</RouterLink>
      <RouterLink to="/forum">论坛</RouterLink>
      <RouterLink to="/blocks">分享</RouterLink>
      <RouterLink v-if="isAdmin" to="/admin/reviews">审核</RouterLink>
    </aside>

    <main class="main-shell">
      <header class="top-bar">
        <div class="top-actions">
          <span class="section-title">{{ currentSectionTitle }}</span>
          <template v-if="isBuilderRoute">
            <button
              type="button"
              data-builder-action="save"
              @click="dispatchBuilderAction('save')"
            >
              保存策略
            </button>
            <button
              type="button"
              data-builder-action="backtest"
              @click="dispatchBuilderAction('backtest')"
            >
              运行回测
            </button>
            <button
              type="button"
              data-builder-action="publish"
              @click="dispatchBuilderAction('publish')"
            >
              发布
            </button>
          </template>
          <form
            v-if="isSharedBlocksRoute"
            class="top-shared-search"
            @submit.prevent="submitSharedBlockTopSearch"
          >
            <input
              v-model="sharedBlockTopSearch"
              class="top-shared-search-input"
              placeholder="搜索公开积木"
              aria-label="搜索公开积木"
            />
            <button class="top-shared-search-button" type="submit">搜索</button>
          </form>
        </div>
        <div class="account-actions">
          <template v-if="authStore.isAuthenticated && authStore.user">
            <span class="account-username" :title="authStore.user.username">
              {{ displayedUsername }}
            </span>
            <button type="button" @click="authStore.logout">退出</button>
          </template>
          <template v-else>
            <button class="account-login-button" type="button" @click="openAuthModal('login')">
              登录
            </button>
            <button class="account-register-button" type="button" @click="openAuthModal('register')">
              注册
            </button>
          </template>
        </div>
      </header>

      <div class="content-area">
        <RouterView />
      </div>
    </main>

    <AuthModal v-model="isAuthModalOpen" :initial-mode="authModalMode" />
  </div>
</template>
