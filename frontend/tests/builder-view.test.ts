import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import BuilderView from '../src/views/BuilderView.vue'

describe('builder view', () => {
  it('renders a dotted canvas with a floating block library', () => {
    const wrapper = mount(BuilderView)

    expect(wrapper.find('.builder-canvas').exists()).toBe(true)
    expect(wrapper.find('.floating-block-library').exists()).toBe(true)
    expect(wrapper.text()).toContain('积木库')
    expect(wrapper.text()).toContain('买入')
    expect(wrapper.text()).toContain('止损')
    expect(wrapper.text()).toContain('风控')
  })

  it('adds a block to the canvas when a library block is dropped', async () => {
    const wrapper = mount(BuilderView)
    const canvas = wrapper.find('.builder-canvas')
    const setData = vi.fn()

    await wrapper.find('[data-block-id="buy"]').trigger('dragstart', {
      dataTransfer: {
        setData,
        effectAllowed: ''
      }
    })

    expect(setData).toHaveBeenCalledWith('application/sts-block', 'buy')

    canvas.element.getBoundingClientRect = vi.fn(() => ({
      left: 100,
      top: 50,
      width: 800,
      height: 600,
      right: 900,
      bottom: 650,
      x: 100,
      y: 50,
      toJSON: () => ({})
    }))

    await canvas.trigger('drop', {
      clientX: 260,
      clientY: 170,
      dataTransfer: {
        getData: vi.fn(() => 'buy')
      }
    })

    const placedBlock = wrapper.find('.canvas-block')
    expect(placedBlock.exists()).toBe(true)
    expect(placedBlock.text()).toContain('买入')
  })

  it('adds a block when a library block is pointer-dragged onto the canvas', async () => {
    const wrapper = mount(BuilderView)
    const canvas = wrapper.find('.builder-canvas')
    canvas.element.getBoundingClientRect = vi.fn(() => ({
      left: 100,
      top: 50,
      width: 800,
      height: 600,
      right: 900,
      bottom: 650,
      x: 100,
      y: 50,
      toJSON: () => ({})
    }))

    const buyBlock = wrapper.find('[data-block-id="buy"]')
    await buyBlock.trigger('pointerdown', { button: 0, pointerId: 1, clientX: 410, clientY: 220 })
    await buyBlock.trigger('pointermove', { pointerId: 1, clientX: 260, clientY: 170 })
    await buyBlock.trigger('pointerup', { pointerId: 1, clientX: 260, clientY: 170 })

    const placedBlocks = wrapper.findAll('.canvas-block')
    expect(placedBlocks).toHaveLength(1)
    expect(placedBlocks[0].text()).toContain('买入')
  })

  it('adds a block when a library block is mouse-dragged onto the canvas', async () => {
    const wrapper = mount(BuilderView)
    const canvas = wrapper.find('.builder-canvas')
    canvas.element.getBoundingClientRect = vi.fn(() => ({
      left: 100,
      top: 50,
      width: 800,
      height: 600,
      right: 900,
      bottom: 650,
      x: 100,
      y: 50,
      toJSON: () => ({})
    }))

    await wrapper
      .find('[data-block-id="buy"]')
      .trigger('mousedown', { button: 0, clientX: 410, clientY: 220 })
    window.dispatchEvent(new MouseEvent('mousemove', { clientX: 260, clientY: 170 }))
    window.dispatchEvent(new MouseEvent('mouseup', { clientX: 260, clientY: 170 }))
    await nextTick()

    const placedBlocks = wrapper.findAll('.canvas-block')
    expect(placedBlocks).toHaveLength(1)
    expect(placedBlocks[0].text()).toContain('买入')
  })

  it('pans the canvas when dragging empty canvas space', async () => {
    const wrapper = mount(BuilderView)
    const canvas = wrapper.find('.builder-canvas')

    await canvas.trigger('pointerdown', { button: 0, pointerId: 1, clientX: 200, clientY: 180 })
    await canvas.trigger('pointermove', { pointerId: 1, clientX: 244, clientY: 214 })
    await canvas.trigger('pointerup', { pointerId: 1, clientX: 244, clientY: 214 })

    expect(wrapper.find('.canvas-world').attributes('style')).toContain('translate(44px, 34px)')
  })

  it('moves the floating block library by dragging its header', async () => {
    const wrapper = mount(BuilderView)
    const header = wrapper.find('.block-library-header')

    await header.trigger('pointerdown', { pointerId: 1, clientX: 430, clientY: 118 })
    await header.trigger('pointermove', { pointerId: 1, clientX: 390, clientY: 150 })
    await header.trigger('pointerup', { pointerId: 1, clientX: 390, clientY: 150 })

    expect(wrapper.find('.floating-block-library').attributes('style')).toContain(
      'translate(-40px, 32px)'
    )
  })

  it('zooms the canvas around the wheel position', async () => {
    const wrapper = mount(BuilderView)
    const canvas = wrapper.find('.builder-canvas')
    canvas.element.getBoundingClientRect = vi.fn(() => ({
      left: 100,
      top: 50,
      width: 800,
      height: 600,
      right: 900,
      bottom: 650,
      x: 100,
      y: 50,
      toJSON: () => ({})
    }))

    canvas.element.dispatchEvent(
      new WheelEvent('wheel', { clientX: 300, clientY: 220, deltaY: -100, bubbles: true })
    )
    await nextTick()

    expect(wrapper.find('.canvas-controls span').text()).toBe('120%')
    expect(wrapper.find('.canvas-world').attributes('style')).toContain('scale(1.197')
  })
})
