<script setup lang="ts">
import { ref, watch } from 'vue'
import { useAuthStore } from '../stores/auth'

type AuthMode = 'login' | 'register'

const props = defineProps<{
  modelValue: boolean
  initialMode: AuthMode
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const authStore = useAuthStore()
const activeMode = ref<AuthMode>(props.initialMode)
const username = ref('')
const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

watch(
  () => props.initialMode,
  (mode) => {
    activeMode.value = mode
  }
)

watch(
  () => props.modelValue,
  (isOpen) => {
    if (isOpen) {
      activeMode.value = props.initialMode
      error.value = ''
    }
  }
)

function closeModal() {
  emit('update:modelValue', false)
}

function switchMode(mode: AuthMode) {
  activeMode.value = mode
  error.value = ''
}

async function submit() {
  error.value = ''
  loading.value = true
  try {
    if (activeMode.value === 'login') {
      await authStore.login(email.value, password.value)
    } else {
      await authStore.register(username.value, email.value, password.value)
    }
    closeModal()
  } catch {
    error.value = activeMode.value === 'login' ? '邮箱或密码错误' : '注册失败，请检查信息'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div
    v-if="modelValue"
    class="auth-modal-backdrop"
    @click.self="closeModal"
    @pointerdown.stop
  >
    <section class="auth-modal" role="dialog" aria-modal="true" aria-labelledby="auth-modal-title">
      <header>
        <div>
          <small>账户</small>
          <h2 id="auth-modal-title">{{ activeMode === 'login' ? '登录' : '创建账户' }}</h2>
        </div>
        <button class="auth-modal-close" type="button" aria-label="关闭登录注册浮窗" @click="closeModal">
          ×
        </button>
      </header>

      <form @submit.prevent="submit">
        <label v-if="activeMode === 'register'">
          用户名
          <input v-model="username" type="text" autocomplete="username" minlength="3" required />
        </label>
        <label>
          邮箱
          <input v-model="email" type="email" autocomplete="email" required />
        </label>
        <label>
          密码
          <input
            v-model="password"
            :autocomplete="activeMode === 'login' ? 'current-password' : 'new-password'"
            type="password"
            minlength="8"
            required
          />
        </label>
        <p v-if="error" class="form-error">{{ error }}</p>
        <button class="auth-modal-submit" type="submit" :disabled="loading">
          {{ loading ? '处理中' : activeMode === 'login' ? '登录' : '注册' }}
        </button>
        <p class="auth-mode-switch">
          <template v-if="activeMode === 'login'">
            没有账户？
            <button class="auth-register-link" type="button" @click="switchMode('register')">
              请先注册
            </button>
          </template>
          <template v-else>
            已有账户？
            <button class="auth-login-link" type="button" @click="switchMode('login')">
              直接登录
            </button>
          </template>
        </p>
      </form>
    </section>
  </div>
</template>
