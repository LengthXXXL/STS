import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from '../src/stores/auth'

vi.mock('../src/api/http', () => ({
  apiClient: {
    post: vi.fn()
  }
}))

import { apiClient } from '../src/api/http'

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('stores user and token after login', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        access_token: 'token-123',
        token_type: 'bearer',
        user: {
          id: 1,
          username: 'alice',
          email: 'alice@example.com',
          roles: ['user']
        }
      }
    })
    const store = useAuthStore()

    await store.login('alice@example.com', 'StrongerPass123')

    expect(store.user?.username).toBe('alice')
    expect(store.token).toBe('token-123')
    expect(localStorage.getItem('sts_access_token')).toBe('token-123')
  })

  it('clears user and token on logout', () => {
    const store = useAuthStore()
    store.setSession({
      token: 'token-123',
      user: { id: 1, username: 'alice', email: 'alice@example.com', roles: ['user'] }
    })

    store.logout()

    expect(store.user).toBeNull()
    expect(store.token).toBeNull()
    expect(localStorage.getItem('sts_access_token')).toBeNull()
  })
})
