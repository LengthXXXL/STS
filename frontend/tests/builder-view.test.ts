import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import BuilderView from '../src/views/BuilderView.vue'

describe('builder view', () => {
  function mockCanvasRect(wrapper: ReturnType<typeof mount>) {
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
    return canvas
  }

  async function dropBlock(wrapper: ReturnType<typeof mount>, blockId: string, clientX: number, clientY: number) {
    const canvas = mockCanvasRect(wrapper)
    await canvas.trigger('drop', {
      clientX,
      clientY,
      dataTransfer: {
        getData: vi.fn(() => blockId)
      }
    })
  }

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
    const canvas = mockCanvasRect(wrapper)
    const setData = vi.fn()

    await wrapper.find('[data-block-id="buy"]').trigger('dragstart', {
      dataTransfer: {
        setData,
        effectAllowed: ''
      }
    })

    expect(setData).toHaveBeenCalledWith('application/sts-block', 'buy')

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
    mockCanvasRect(wrapper)

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
    mockCanvasRect(wrapper)

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

  it('cancels mouse block dragging when the window loses focus', async () => {
    const wrapper = mount(BuilderView)
    await wrapper
      .find('[data-block-id="buy"]')
      .trigger('mousedown', { button: 0, clientX: 410, clientY: 220 })

    expect(wrapper.find('.drag-preview').exists()).toBe(true)

    window.dispatchEvent(new Event('blur'))
    await nextTick()

    expect(wrapper.find('.drag-preview').exists()).toBe(false)
  })

  it('moves a placed block by dragging it on the canvas', async () => {
    const wrapper = mount(BuilderView)
    mockCanvasRect(wrapper)
    await dropBlock(wrapper, 'buy', 260, 170)

    const placedBlock = wrapper.find('.canvas-block')
    await placedBlock.trigger('pointerdown', { button: 0, pointerId: 2, clientX: 260, clientY: 170 })
    await placedBlock.trigger('pointermove', { pointerId: 2, clientX: 332, clientY: 218 })
    await placedBlock.trigger('pointerup', { pointerId: 2, clientX: 332, clientY: 218 })

    expect(wrapper.find('.canvas-block').attributes('style')).toContain('translate(240px, 168px)')
  })

  it('deletes a selected placed block and its connections', async () => {
    const wrapper = mount(BuilderView)
    await dropBlock(wrapper, 'buy', 260, 170)

    await wrapper.find('.canvas-block').trigger('click')
    await wrapper.find('.canvas-block-delete').trigger('click')

    expect(wrapper.findAll('.canvas-block')).toHaveLength(0)
  })

  it('connects an output port to an input port', async () => {
    const wrapper = mount(BuilderView)
    mockCanvasRect(wrapper)
    await dropBlock(wrapper, 'buy', 260, 170)
    await dropBlock(wrapper, 'sell', 460, 260)

    const outputPort = wrapper.find('[data-port="output"]')
    const inputPorts = wrapper.findAll('[data-port="input"]')
    await outputPort.trigger('pointerdown', { pointerId: 3, clientX: 288, clientY: 194 })
    await wrapper.find('.builder-canvas').trigger('pointermove', {
      pointerId: 3,
      clientX: 360,
      clientY: 238
    })
    await inputPorts[1].trigger('pointerup', { pointerId: 3, clientX: 460, clientY: 260 })

    expect(wrapper.find('.connection-path').exists()).toBe(true)
  })

  it('toggles magnetic snapping for component movement', async () => {
    const wrapper = mount(BuilderView)
    mockCanvasRect(wrapper)
    await dropBlock(wrapper, 'buy', 260, 170)
    await dropBlock(wrapper, 'sell', 420, 265)

    const secondBlock = wrapper.findAll('.canvas-block')[1]
    await secondBlock.trigger('pointerdown', { button: 0, pointerId: 4, clientX: 420, clientY: 265 })
    await secondBlock.trigger('pointermove', { pointerId: 4, clientX: 468, clientY: 178 })
    await secondBlock.trigger('pointerup', { pointerId: 4, clientX: 468, clientY: 178 })

    expect(wrapper.findAll('.canvas-block')[1].attributes('style')).toContain('translate(360px, 120px)')

    await wrapper.find('.snap-toggle').trigger('click')
    await secondBlock.trigger('pointerdown', { button: 0, pointerId: 5, clientX: 468, clientY: 178 })
    await secondBlock.trigger('pointermove', { pointerId: 5, clientX: 505, clientY: 205 })
    await secondBlock.trigger('pointerup', { pointerId: 5, clientX: 505, clientY: 205 })

    expect(wrapper.findAll('.canvas-block')[1].attributes('style')).toContain('translate(397px, 147px)')
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
