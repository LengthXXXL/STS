import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it } from 'vitest'
import App from '../src/App.vue'
import { useAuthStore } from '../src/stores/auth'

describe('app shell', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('shows logged-out and logged-in account states', async () => {
    const pinia = createPinia()
    const wrapper = mount(App, {
      global: {
        plugins: [pinia],
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
          RouterView: { template: '<main />' }
        }
      }
    })
    const authStore = useAuthStore()

    expect(wrapper.text()).toContain('保存策略')
    expect(wrapper.text()).toContain('运行回测')
    expect(wrapper.text()).toContain('发布')
    expect(wrapper.text()).toContain('登录')
    expect(wrapper.text()).toContain('注册')

    authStore.setSession({
      token: 'token-123',
      user: { id: 1, username: 'alice', email: 'alice@example.com', roles: ['user'] }
    })
    await nextTick()

    expect(wrapper.text()).toContain('alice')
    expect(wrapper.text()).toContain('退出')
    expect(wrapper.text()).not.toContain('注册')

    const logoutButton = wrapper.findAll('button').find((button) => button.text() === '退出')
    expect(logoutButton).toBeTruthy()
    await logoutButton?.trigger('click')

    expect(authStore.user).toBeNull()
    expect(authStore.token).toBeNull()
    expect(localStorage.getItem('sts_access_token')).toBeNull()
  })
})
