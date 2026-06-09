import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AuthModal from '../src/components/AuthModal.vue'
import { useAuthStore } from '../src/stores/auth'

enableAutoUnmount(afterEach)

describe('auth modal', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('shows a clear duplicate email message when registration is rejected by the API', async () => {
    const wrapper = mount(AuthModal, {
      props: {
        modelValue: true,
        initialMode: 'register'
      },
      global: {
        plugins: [createPinia()]
      }
    })
    const authStore = useAuthStore()
    vi.spyOn(authStore, 'register').mockRejectedValueOnce({
      isAxiosError: true,
      response: { data: { detail: 'Email already registered' } }
    })

    await wrapper.find('input[autocomplete="username"]').setValue('alice')
    await wrapper.find('input[autocomplete="email"]').setValue('alice@example.com')
    await wrapper.find('input[autocomplete="new-password"]').setValue('StrongerPass123')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.find('.form-error').text()).toBe('邮箱已被注册，请换一个邮箱')
  })

  it('shows a clear duplicate username message when registration is rejected by the API', async () => {
    const wrapper = mount(AuthModal, {
      props: {
        modelValue: true,
        initialMode: 'register'
      },
      global: {
        plugins: [createPinia()]
      }
    })
    const authStore = useAuthStore()
    vi.spyOn(authStore, 'register').mockRejectedValueOnce({
      isAxiosError: true,
      response: { data: { detail: 'Username already registered' } }
    })

    await wrapper.find('input[autocomplete="username"]').setValue('alice')
    await wrapper.find('input[autocomplete="email"]').setValue('alice2@example.com')
    await wrapper.find('input[autocomplete="new-password"]').setValue('StrongerPass123')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.find('.form-error').text()).toBe('用户名已被使用，请换一个用户名')
  })
})
