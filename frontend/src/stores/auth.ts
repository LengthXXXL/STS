import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { apiClient } from '../api/http'

export interface AuthUser {
  id: number
  username: string
  email: string
  roles: string[]
}

interface AuthResponse {
  access_token: string
  token_type: string
  user: AuthUser
}

interface SessionPayload {
  token: string
  user: AuthUser
}

const TOKEN_KEY = 'sts_access_token'
const USER_KEY = 'sts_user'

function readStoredUser(): AuthUser | null {
  const storedUser = localStorage.getItem(USER_KEY)
  if (!storedUser) {
    return null
  }

  try {
    return JSON.parse(storedUser) as AuthUser
  } catch {
    localStorage.removeItem(USER_KEY)
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const user = ref<AuthUser | null>(readStoredUser())
  const isAuthenticated = computed(() => Boolean(token.value && user.value))

  function setSession(payload: SessionPayload) {
    token.value = payload.token
    user.value = payload.user
    localStorage.setItem(TOKEN_KEY, payload.token)
    localStorage.setItem(USER_KEY, JSON.stringify(payload.user))
  }

  async function login(email: string, password: string) {
    const response = await apiClient.post<AuthResponse>('/auth/login', { email, password })
    setSession({ token: response.data.access_token, user: response.data.user })
  }

  async function register(username: string, email: string, password: string) {
    const response = await apiClient.post<AuthResponse>('/auth/register', {
      username,
      email,
      password
    })
    setSession({ token: response.data.access_token, user: response.data.user })
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  }

  return {
    token,
    user,
    isAuthenticated,
    setSession,
    login,
    register,
    logout
  }
})
