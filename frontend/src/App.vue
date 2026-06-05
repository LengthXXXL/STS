<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import AuthModal from './components/AuthModal.vue'
import { useAuthStore } from './stores/auth'

type AuthMode = 'login' | 'register'

const authStore = useAuthStore()
const isAuthModalOpen = ref(false)
const authModalMode = ref<AuthMode>('login')

const displayedUsername = computed(() => {
  const username = authStore.user?.username ?? ''
  return username.length > 6 ? username.slice(-6) : username
})

function dispatchBuilderAction(action: 'save' | 'backtest' | 'publish') {
  window.dispatchEvent(new CustomEvent('sts:builder-action', { detail: { action } }))
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
    </aside>

    <main class="main-shell">
      <header class="top-bar">
        <div class="top-actions">
          <span class="section-title">策略工作台</span>
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
