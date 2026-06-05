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

  function mockLibraryRect(wrapper: ReturnType<typeof mount>) {
    const library = wrapper.find('.floating-block-library')
    library.element.getBoundingClientRect = vi.fn(() => ({
      left: 300,
      top: 80,
      width: 280,
      height: 420,
      right: 580,
      bottom: 500,
      x: 300,
      y: 80,
      toJSON: () => ({})
    }))
    return library
  }

  function dispatchPointerWindowEvent(
    type: string,
    options: { pointerId: number; clientX?: number; clientY?: number }
  ) {
    const event = new Event(type, { bubbles: true }) as PointerEvent
    Object.defineProperties(event, {
      pointerId: { value: options.pointerId },
      clientX: { value: options.clientX ?? 0 },
      clientY: { value: options.clientY ?? 0 }
    })
    window.dispatchEvent(event)
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

  it('shows editable parameters for a selected placed block', async () => {
    const wrapper = mount(BuilderView)
    await dropBlock(wrapper, 'buy', 260, 170)

    await wrapper.find('.canvas-block').trigger('click')

    const inspector = wrapper.find('.block-inspector')
    expect(inspector.exists()).toBe(true)
    expect(inspector.text()).toContain('买入')
    expect(inspector.text()).not.toContain('股票代码')
    expect(inspector.text()).toContain('买入仓位')

    const sizeInput = wrapper.find('[data-param-key="sizePercent"]')
    expect((sizeInput.element as HTMLInputElement).value).toBe('20')

    await sizeInput.setValue('35')

    expect((wrapper.find('[data-param-key="sizePercent"]').element as HTMLInputElement).value).toBe(
      '35'
    )
  })

  it('filters the block library by the search keyword', async () => {
    const wrapper = mount(BuilderView)

    expect(wrapper.findAll('.library-block')).toHaveLength(6)

    await wrapper.find('.block-library-search').setValue('止损')

    const visibleBlocks = wrapper.findAll('.library-block')
    expect(visibleBlocks).toHaveLength(1)
    expect(visibleBlocks[0].text()).toContain('止损')

    await wrapper.find('.block-library-search').setValue('动作')

    expect(wrapper.findAll('.library-block')).toHaveLength(3)
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

  it('finishes pointer block dragging from a window pointerup event', async () => {
    const wrapper = mount(BuilderView)
    mockCanvasRect(wrapper)

    await wrapper
      .find('[data-block-id="buy"]')
      .trigger('pointerdown', { button: 0, pointerId: 8, clientX: 410, clientY: 220 })
    dispatchPointerWindowEvent('pointermove', { pointerId: 8, clientX: 260, clientY: 170 })
    dispatchPointerWindowEvent('pointerup', { pointerId: 8, clientX: 260, clientY: 170 })
    await nextTick()

    const placedBlocks = wrapper.findAll('.canvas-block')
    expect(placedBlocks).toHaveLength(1)
    expect(placedBlocks[0].text()).toContain('买入')
    expect(wrapper.find('.drag-preview').exists()).toBe(false)
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

  it('does not add a block when library drag ends inside the library panel', async () => {
    const wrapper = mount(BuilderView)
    mockCanvasRect(wrapper)
    mockLibraryRect(wrapper)

    await wrapper
      .find('[data-block-id="buy"]')
      .trigger('mousedown', { button: 0, clientX: 410, clientY: 220 })
    window.dispatchEvent(new MouseEvent('mouseup', { clientX: 410, clientY: 220 }))
    await nextTick()

    expect(wrapper.findAll('.canvas-block')).toHaveLength(0)
    expect(wrapper.find('.drag-preview').exists()).toBe(false)
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

  it('cancels pointer block dragging when the window loses focus', async () => {
    const wrapper = mount(BuilderView)

    await wrapper
      .find('[data-block-id="buy"]')
      .trigger('pointerdown', { button: 0, pointerId: 9, clientX: 410, clientY: 220 })

    expect(wrapper.find('.drag-preview').exists()).toBe(true)

    window.dispatchEvent(new Event('blur'))
    await nextTick()

    expect(wrapper.find('.drag-preview').exists()).toBe(false)
  })

  it('cancels pointer block dragging from a pointercancel event', async () => {
    const wrapper = mount(BuilderView)
    mockCanvasRect(wrapper)

    await wrapper
      .find('[data-block-id="buy"]')
      .trigger('pointerdown', { button: 0, pointerId: 10, clientX: 410, clientY: 220 })

    expect(wrapper.find('.drag-preview').exists()).toBe(true)

    await wrapper
      .find('[data-block-id="buy"]')
      .trigger('pointercancel', { pointerId: 10, clientX: 260, clientY: 170 })
    await nextTick()

    expect(wrapper.findAll('.canvas-block')).toHaveLength(0)
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

  it('deletes a placed block and its connections from its context menu', async () => {
    const wrapper = mount(BuilderView)
    mockCanvasRect(wrapper)
    await dropBlock(wrapper, 'buy', 260, 170)
    await dropBlock(wrapper, 'sell', 460, 260)

    const outputPort = wrapper.find('[data-port="output"]')
    const inputPorts = wrapper.findAll('[data-port="input"]')
    await outputPort.trigger('pointerdown', { pointerId: 3, clientX: 288, clientY: 194 })
    await inputPorts[1].trigger('pointerup', { pointerId: 3, clientX: 460, clientY: 260 })
    expect(wrapper.find('.connection-path').exists()).toBe(true)

    expect(wrapper.find('.canvas-block-delete').exists()).toBe(false)

    await wrapper.find('.canvas-block').trigger('contextmenu', { clientX: 260, clientY: 170 })
    expect(wrapper.find('.context-menu').exists()).toBe(true)
    expect(wrapper.find('.block-inspector').exists()).toBe(false)

    await wrapper.find('.context-menu-delete').trigger('click')

    expect(wrapper.findAll('.canvas-block')).toHaveLength(1)
    expect(wrapper.find('.connection-path').exists()).toBe(false)
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

  it('deletes a connection from its context menu', async () => {
    const wrapper = mount(BuilderView)
    mockCanvasRect(wrapper)
    await dropBlock(wrapper, 'buy', 260, 170)
    await dropBlock(wrapper, 'sell', 460, 260)

    const outputPort = wrapper.find('[data-port="output"]')
    const inputPorts = wrapper.findAll('[data-port="input"]')
    await outputPort.trigger('pointerdown', { pointerId: 3, clientX: 288, clientY: 194 })
    await inputPorts[1].trigger('pointerup', { pointerId: 3, clientX: 460, clientY: 260 })
    expect(wrapper.find('.connection-path').exists()).toBe(true)

    await wrapper.find('.connection-path').trigger('contextmenu', { clientX: 360, clientY: 220 })
    await wrapper.find('.context-menu-delete').trigger('click')

    expect(wrapper.find('.connection-path').exists()).toBe(false)
  })

  it('clears placed blocks, connections, and context menu from the canvas controls', async () => {
    const wrapper = mount(BuilderView)
    mockCanvasRect(wrapper)
    await dropBlock(wrapper, 'buy', 260, 170)
    await dropBlock(wrapper, 'sell', 460, 260)

    const outputPort = wrapper.find('[data-port="output"]')
    const inputPorts = wrapper.findAll('[data-port="input"]')
    await outputPort.trigger('pointerdown', { pointerId: 3, clientX: 288, clientY: 194 })
    await inputPorts[1].trigger('pointerup', { pointerId: 3, clientX: 460, clientY: 260 })
    await wrapper.find('.canvas-block').trigger('contextmenu', { clientX: 260, clientY: 170 })

    expect(wrapper.findAll('.canvas-block')).toHaveLength(2)
    expect(wrapper.find('.connection-path').exists()).toBe(true)
    expect(wrapper.find('.context-menu').exists()).toBe(true)
    expect(wrapper.find('.block-inspector').exists()).toBe(false)

    await wrapper.find('.clear-canvas-button').trigger('click')

    expect(wrapper.findAll('.canvas-block')).toHaveLength(0)
    expect(wrapper.find('.connection-path').exists()).toBe(false)
    expect(wrapper.find('.context-menu').exists()).toBe(false)
    expect(wrapper.find('.block-inspector').exists()).toBe(false)
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
