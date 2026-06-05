<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await authStore.login(email.value, password.value)
    await router.push('/')
  } catch {
    error.value = '邮箱或密码错误'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="auth-card">
    <h1>登录</h1>
    <form @submit.prevent="submit">
      <label>
        邮箱
        <input v-model="email" type="email" autocomplete="email" required />
      </label>
      <label>
        密码
        <input v-model="password" type="password" autocomplete="current-password" required />
      </label>
      <p v-if="error" class="form-error">{{ error }}</p>
      <button type="submit" :disabled="loading">{{ loading ? '登录中' : '登录' }}</button>
    </form>
  </section>
</template>
