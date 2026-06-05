import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import BuilderView from '../src/views/BuilderView.vue'

describe('builder view', () => {
  it('renders a dotted canvas with a floating block library', () => {
    const wrapper = mount(BuilderView)

    expect(wrapper.find('.builder-canvas').exists()).toBe(true)
    expect(wrapper.find('.floating-block-library').exists()).toBe(true)
    expect(wrapper.text()).toContain('积木库')
    expect(wrapper.text()).toContain('条件')
    expect(wrapper.text()).toContain('风控')
  })
})
