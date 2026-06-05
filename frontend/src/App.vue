<script setup lang="ts">
import { useAuthStore } from './stores/auth'

const authStore = useAuthStore()

function dispatchBuilderAction(action: 'save' | 'backtest' | 'publish') {
  window.dispatchEvent(new CustomEvent('sts:builder-action', { detail: { action } }))
}
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
            <span>{{ authStore.user.username }}</span>
            <button type="button" @click="authStore.logout">退出</button>
          </template>
          <template v-else>
            <RouterLink to="/login">登录</RouterLink>
            <RouterLink to="/register">注册</RouterLink>
          </template>
        </div>
      </header>

      <div class="content-area">
        <RouterView />
      </div>
    </main>
  </div>
</template>
