<script setup lang="ts">
import { useAuthStore } from './stores/auth'

const authStore = useAuthStore()
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
          <span class="section-title">Simulated Trading System</span>
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

      <div class="content-grid">
        <RouterView />
        <aside class="block-library" aria-label="积木库">
          <h2>积木库</h2>
          <input placeholder="搜索积木" />
          <nav>
            <button>条件</button>
            <button>指标</button>
            <button>动作</button>
            <button>风控</button>
            <button>自定义</button>
          </nav>
        </aside>
      </div>
    </main>
  </div>
</template>
