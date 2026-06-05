<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const username = ref('')
const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await authStore.register(username.value, email.value, password.value)
    await router.push('/')
  } catch {
    error.value = '注册失败，请检查用户名、邮箱或密码'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="auth-card">
    <h1>注册</h1>
    <form @submit.prevent="submit">
      <label>
        用户名
        <input v-model="username" type="text" autocomplete="username" minlength="3" required />
      </label>
      <label>
        邮箱
        <input v-model="email" type="email" autocomplete="email" required />
      </label>
      <label>
        密码
        <input v-model="password" type="password" autocomplete="new-password" minlength="8" required />
      </label>
      <p v-if="error" class="form-error">{{ error }}</p>
      <button type="submit" :disabled="loading">{{ loading ? '注册中' : '注册' }}</button>
    </form>
  </section>
</template>
