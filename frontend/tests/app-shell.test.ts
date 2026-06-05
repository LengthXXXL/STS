import { enableAutoUnmount, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const routeMock = vi.hoisted(() => ({
  name: 'builder',
  path: '/'
}))

vi.mock('vue-router', async () => {
  const actual = await vi.importActual<typeof import('vue-router')>('vue-router')

  return {
    ...actual,
    useRoute: () => routeMock
  }
})

import App from '../src/App.vue'
import { useAuthStore } from '../src/stores/auth'

enableAutoUnmount(afterEach)

describe('app shell', () => {
  beforeEach(() => {
    localStorage.clear()
    routeMock.name = 'builder'
    routeMock.path = '/'
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
      user: {
        id: 1,
        username: 'super_long_alice_123456',
        email: 'alice@example.com',
        roles: ['user']
      }
    })
    await nextTick()

    const username = wrapper.find('.account-username')
    expect(username.text()).toBe('123456')
    expect(username.attributes('title')).toBe('super_long_alice_123456')
    expect(wrapper.text()).toContain('退出')
    expect(wrapper.text()).not.toContain('注册')

    const logoutButton = wrapper.findAll('button').find((button) => button.text() === '退出')
    expect(logoutButton).toBeTruthy()
    await logoutButton?.trigger('click')

    expect(authStore.user).toBeNull()
    expect(authStore.token).toBeNull()
    expect(localStorage.getItem('sts_access_token')).toBeNull()
  })

  it('opens the login and register modal from account actions and auth-required events', async () => {
    const wrapper = mount(App, {
      global: {
        plugins: [createPinia()],
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
          RouterView: { template: '<main />' }
        }
      }
    })

    await wrapper.find('.account-login-button').trigger('click')
    expect(wrapper.find('.auth-modal').exists()).toBe(true)
    expect(wrapper.find('.auth-modal').text()).toContain('登录')
    expect(wrapper.find('.auth-modal-submit').text()).toBe('登录')
    expect(wrapper.find('.auth-mode-switch').text()).toContain('没有账户？')
    expect(wrapper.find('.auth-register-link').text()).toBe('请先注册')
    expect(wrapper.find('.auth-modal-tabs').exists()).toBe(false)

    await wrapper.find('.auth-register-link').trigger('click')
    expect(wrapper.find('.auth-modal').text()).toContain('创建账户')
    expect(wrapper.find('.auth-modal-submit').text()).toBe('注册')
    expect(wrapper.find('.auth-mode-switch').text()).toContain('已有账户？')
    expect(wrapper.find('.auth-login-link').text()).toBe('直接登录')

    await wrapper.find('.auth-login-link').trigger('click')
    expect(wrapper.find('.auth-modal').text()).toContain('登录')

    await wrapper.find('.auth-modal-close').trigger('click')
    expect(wrapper.find('.auth-modal').exists()).toBe(false)

    window.dispatchEvent(new CustomEvent('sts:auth-required'))
    await nextTick()

    expect(wrapper.find('.auth-modal').exists()).toBe(true)
    expect(wrapper.find('.auth-modal-submit').text()).toBe('登录')
  })

  it('dispatches builder actions from the top bar', async () => {
    const wrapper = mount(App, {
      global: {
        plugins: [createPinia()],
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
          RouterView: { template: '<main />' }
        }
      }
    })
    const receivedActions: string[] = []
    const listener = vi.fn((event: Event) => {
      receivedActions.push((event as CustomEvent<{ action: string }>).detail.action)
    })
    window.addEventListener('sts:builder-action', listener)

    await wrapper.find('[data-builder-action="save"]').trigger('click')
    await wrapper.find('[data-builder-action="backtest"]').trigger('click')
    await wrapper.find('[data-builder-action="publish"]').trigger('click')

    expect(receivedActions).toEqual(['save', 'backtest', 'publish'])

    window.removeEventListener('sts:builder-action', listener)
  })

  it('hides builder actions outside the builder route', () => {
    routeMock.name = 'space'
    routeMock.path = '/space'

    const wrapper = mount(App, {
      global: {
        plugins: [createPinia()],
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
          RouterView: { template: '<main />' }
        }
      }
    })

    expect(wrapper.find('.section-title').text()).toBe('个人空间')
    expect(wrapper.find('[data-builder-action="save"]').exists()).toBe(false)
    expect(wrapper.find('[data-builder-action="backtest"]').exists()).toBe(false)
    expect(wrapper.find('[data-builder-action="publish"]').exists()).toBe(false)
  })
})
