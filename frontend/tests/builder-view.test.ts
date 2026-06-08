import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { apiClient } from '../src/api/http'
import { useAuthStore } from '../src/stores/auth'
import { useStrategyWorkspaceStore } from '../src/stores/strategyWorkspace'
import BuilderView from '../src/views/BuilderView.vue'

const builderPushMock = vi.hoisted(() => vi.fn())

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: builderPushMock
  })
}))

vi.mock('../src/api/http', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn()
  }
}))

enableAutoUnmount(afterEach)

describe('builder view', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.resetAllMocks()
  })

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

  async function openReviewModal(action: 'backtest' | 'publish' = 'backtest') {
    window.dispatchEvent(new CustomEvent('sts:builder-action', { detail: { action } }))
    await nextTick()
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

  const savedCustomBlockTemplate = {
    id: 21,
    ownerId: 1,
    name: '突破止盈模板',
    description: '买入后按目标止盈',
    category: '风控',
    tags: ['止盈'],
    template: {
      version: 1,
      nodes: [
        {
          id: 'template-buy',
          type: 'buy',
          label: '买入',
          x: 0,
          y: 0,
          params: { sizePercent: '30', orderType: 'market' }
        },
        {
          id: 'template-take-profit',
          type: 'take-profit',
          label: '止盈',
          x: 180,
          y: 0,
          params: { profitRate: '5', sellPercent: '100' }
        }
      ],
      edges: [{ id: 'template-edge', from: 'template-buy', to: 'template-take-profit' }],
      viewport: { x: 0, y: 0, scale: 1 }
    },
    reviewStatus: 'private',
    createdAt: '2026-06-06T11:00:00',
    updatedAt: '2026-06-06T11:30:00'
  }

  function mockCustomBlockLibrary(items = [savedCustomBlockTemplate]) {
    vi.mocked(apiClient.get).mockImplementation((url) => {
      if (url === '/custom-blocks') {
        return Promise.resolve({
          data: {
            items,
            total: items.length,
            page: 1,
            pageSize: 50
          }
        })
      }

      return Promise.resolve({
        data: {
          items: [],
          total: 0,
          page: 1,
          pageSize: 50
        }
      })
    })
  }

  it('renders a dotted canvas with a floating block library', () => {
    const wrapper = mount(BuilderView)

    expect(wrapper.find('.builder-canvas').exists()).toBe(true)
    expect(wrapper.find('.floating-block-library').exists()).toBe(true)
    expect(wrapper.findAll('.block-library-group')).toHaveLength(6)
    expect(wrapper.find('.block-library').text()).toContain('行情指标')
    expect(wrapper.find('.block-library').text()).toContain('持仓')
    expect(wrapper.find('.block-library').text()).toContain('时间')
    expect(wrapper.find('.strategy-draft-panel').exists()).toBe(false)
    expect(wrapper.find('.strategy-review-modal').exists()).toBe(false)
    expect(wrapper.text()).toContain('积木库')
    expect(wrapper.text()).toContain('买入')
    expect(wrapper.text()).toContain('如果')
    expect(wrapper.text()).toContain('N根收益率')
    expect(wrapper.text()).toContain('移动止损')
    expect(wrapper.text()).toContain('止损')
    expect(wrapper.text()).toContain('风控')
  })

  it('collapses and expands the floating block library from its arrow button', async () => {
    const wrapper = mount(BuilderView)

    expect(wrapper.find('.block-library-search').exists()).toBe(true)
    expect(wrapper.findAll('.block-library-group')).toHaveLength(6)
    expect(wrapper.find('.floating-block-library').classes()).not.toContain('is-collapsed')

    await wrapper.find('.block-library-collapse-toggle').trigger('click')

    expect(wrapper.find('.floating-block-library').classes()).toContain('is-collapsed')
    expect(wrapper.find('.block-library-search').exists()).toBe(false)
    expect(wrapper.findAll('.block-library-group')).toHaveLength(0)
    expect(wrapper.find('.block-library-collapse-toggle').attributes('aria-label')).toBe(
      '展开积木库'
    )

    await wrapper.find('.block-library-collapse-toggle').trigger('click')

    expect(wrapper.find('.floating-block-library').classes()).not.toContain('is-collapsed')
    expect(wrapper.find('.block-library-search').exists()).toBe(true)
    expect(wrapper.findAll('.block-library-group')).toHaveLength(6)
    expect(wrapper.find('.block-library-collapse-toggle').attributes('aria-label')).toBe(
      '收起积木库'
    )
  })

  it('shows strategy preview only when running a backtest or publishing', async () => {
    const wrapper = mount(BuilderView)

    expect(wrapper.find('.strategy-review-modal').exists()).toBe(false)

    await openReviewModal('backtest')

    expect(wrapper.find('.strategy-review-modal').exists()).toBe(true)
    expect(wrapper.find('.strategy-review-modal').text()).toContain('运行回测前检查')
    expect(wrapper.find('.strategy-json-preview').exists()).toBe(true)
    expect(wrapper.find('.backtest-config-preview').exists()).toBe(true)

    await wrapper.find('.strategy-review-close').trigger('click')
    expect(wrapper.find('.strategy-review-modal').exists()).toBe(false)

    await openReviewModal('publish')

    expect(wrapper.find('.strategy-review-modal').exists()).toBe(true)
    expect(wrapper.find('.strategy-review-modal').text()).toContain('发布前检查')
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

  it('opens editable parameters only from a placed block right-click', async () => {
    const wrapper = mount(BuilderView)
    await dropBlock(wrapper, 'buy', 260, 170)

    await wrapper.find('.canvas-block').trigger('click')

    expect(wrapper.find('.canvas-block').classes()).toContain('is-selected')
    expect(wrapper.find('.block-inspector').exists()).toBe(false)

    await wrapper.find('.canvas-block').trigger('contextmenu', { clientX: 260, clientY: 170 })

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

    expect(wrapper.findAll('.library-block')).toHaveLength(14)

    await wrapper.find('.block-library-search').setValue('移动')

    const visibleBlocks = wrapper.findAll('.library-block')
    expect(visibleBlocks).toHaveLength(1)
    expect(visibleBlocks[0].text()).toContain('移动止损')

    await wrapper.find('.block-library-search').setValue('动作')

    expect(wrapper.findAll('.library-block')).toHaveLength(3)
  })

  it('loads authenticated custom block templates into the block library', async () => {
    const authStore = useAuthStore()
    authStore.setSession({
      token: 'token-123',
      user: { id: 1, username: 'alice', email: 'alice@example.com', roles: ['user'] }
    })
    mockCustomBlockLibrary()

    const wrapper = mount(BuilderView)
    await flushPromises()

    expect(apiClient.get).toHaveBeenCalledWith('/custom-blocks', {
      params: { page: 1, pageSize: 50 }
    })
    expect(wrapper.text()).toContain('我的积木')
    expect(wrapper.text()).toContain('突破止盈模板')
    expect(wrapper.find('[data-custom-block-id="21"]').exists()).toBe(true)

    await wrapper.find('.block-library-search').setValue('止盈模板')

    expect(wrapper.findAll('.custom-library-block')).toHaveLength(1)
    expect(wrapper.find('.custom-library-block').text()).toContain('突破止盈模板')
  })

  it('disambiguates historical duplicate custom block names in the library', async () => {
    const authStore = useAuthStore()
    authStore.setSession({
      token: 'token-123',
      user: { id: 1, username: 'alice', email: 'alice@example.com', roles: ['user'] }
    })
    mockCustomBlockLibrary([
      { ...savedCustomBlockTemplate, id: 21, name: '未命名积木模板' },
      { ...savedCustomBlockTemplate, id: 22, name: '未命名积木模板' }
    ])

    const wrapper = mount(BuilderView)
    await flushPromises()

    const customBlocks = wrapper.findAll('.custom-library-block')
    expect(customBlocks).toHaveLength(2)
    expect(customBlocks[0].text()).toContain('未命名积木模板 #21')
    expect(customBlocks[1].text()).toContain('未命名积木模板 #22')
  })

  it('inserts a custom block template with remapped nodes and connections', async () => {
    const authStore = useAuthStore()
    authStore.setSession({
      token: 'token-123',
      user: { id: 1, username: 'alice', email: 'alice@example.com', roles: ['user'] }
    })
    mockCustomBlockLibrary()
    const wrapper = mount(BuilderView)
    mockCanvasRect(wrapper)
    await flushPromises()

    await wrapper
      .find('[data-custom-block-id="21"]')
      .trigger('mousedown', { button: 0, clientX: 410, clientY: 220 })
    window.dispatchEvent(new MouseEvent('mousemove', { clientX: 260, clientY: 170 }))
    window.dispatchEvent(new MouseEvent('mouseup', { clientX: 260, clientY: 170 }))
    await nextTick()

    const placedBlocks = wrapper.findAll('.canvas-block')
    expect(placedBlocks).toHaveLength(2)
    expect(placedBlocks[0].text()).toContain('买入')
    expect(placedBlocks[1].text()).toContain('止盈')

    await openReviewModal('publish')
    const strategy = JSON.parse(wrapper.find('.strategy-json-preview').text())

    expect(strategy.nodes).toHaveLength(2)
    expect(strategy.edges).toHaveLength(1)
    expect(strategy.nodes.map((node: { id: string }) => node.id)).not.toContain('template-buy')
    expect(strategy.edges[0].from).toBe(strategy.nodes[0].id)
    expect(strategy.edges[0].to).toBe(strategy.nodes[1].id)
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

  it('does not open the parameter inspector while moving a placed block', async () => {
    const wrapper = mount(BuilderView)
    mockCanvasRect(wrapper)
    await dropBlock(wrapper, 'buy', 260, 170)

    const placedBlock = wrapper.find('.canvas-block')
    await placedBlock.trigger('pointerdown', { button: 0, pointerId: 12, clientX: 260, clientY: 170 })
    await placedBlock.trigger('pointermove', { pointerId: 12, clientX: 320, clientY: 210 })
    await placedBlock.trigger('pointerup', { pointerId: 12, clientX: 320, clientY: 210 })
    await wrapper.find('.canvas-block').trigger('click')

    expect(wrapper.find('.block-inspector').exists()).toBe(false)

    await wrapper.find('.canvas-block').trigger('contextmenu', { clientX: 320, clientY: 210 })

    expect(wrapper.find('.block-inspector').exists()).toBe(true)
  })

  it('deletes a selected placed block and its connections from the parameter inspector', async () => {
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
    expect(wrapper.find('.block-inspector').exists()).toBe(true)

    await wrapper.find('.block-inspector-delete').trigger('click')

    expect(wrapper.findAll('.canvas-block')).toHaveLength(1)
    expect(wrapper.find('.connection-path').exists()).toBe(false)
    expect(wrapper.find('.block-inspector').exists()).toBe(false)
  })

  it('opens the parameter inspector instead of a delete menu when a placed block is right-clicked', async () => {
    const wrapper = mount(BuilderView)
    mockCanvasRect(wrapper)
    await dropBlock(wrapper, 'buy', 260, 170)

    await wrapper.find('.canvas-block').trigger('contextmenu', { clientX: 260, clientY: 170 })

    expect(wrapper.find('.context-menu').exists()).toBe(false)
    expect(wrapper.find('.block-inspector').exists()).toBe(true)
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

  it('renders strategy JSON with placed block params and connections', async () => {
    const wrapper = mount(BuilderView)
    mockCanvasRect(wrapper)
    await dropBlock(wrapper, 'buy', 260, 170)
    await dropBlock(wrapper, 'sell', 460, 260)

    await wrapper.find('.canvas-block').trigger('contextmenu', { clientX: 260, clientY: 170 })
    await wrapper.find('[data-param-key="sizePercent"]').setValue('35')

    const outputPort = wrapper.find('[data-port="output"]')
    const inputPorts = wrapper.findAll('[data-port="input"]')
    await outputPort.trigger('pointerdown', { pointerId: 3, clientX: 288, clientY: 194 })
    await inputPorts[1].trigger('pointerup', { pointerId: 3, clientX: 460, clientY: 260 })

    await openReviewModal()

    const strategy = JSON.parse(wrapper.find('.strategy-json-preview').text())

    expect(strategy.version).toBe(1)
    expect(strategy.nodes).toHaveLength(2)
    expect(strategy.edges).toHaveLength(1)
    expect(strategy.nodes[0]).toMatchObject({
      type: 'buy',
      label: '买入',
      params: {
        sizePercent: '35',
        orderType: 'market'
      }
    })
    expect(strategy.edges[0]).toMatchObject({
      from: strategy.nodes[0].id,
      to: strategy.nodes[1].id
    })
  })

  it('saves and loads a local strategy draft', async () => {
    const wrapper = mount(BuilderView)
    mockCanvasRect(wrapper)
    await dropBlock(wrapper, 'buy', 260, 170)
    await openReviewModal()

    expect(wrapper.find('.draft-storage-hint').text()).toContain('本机浏览器')
    expect(wrapper.find('.draft-storage-hint').text()).toContain('不会同步到账户')

    await wrapper.find('.save-draft-button').trigger('click')
    expect(localStorage.getItem('sts.builder.strategyDraft.v1')).toContain('"nodes"')
    expect(wrapper.find('.draft-status').text()).toContain('本机浏览器')

    await wrapper.find('.clear-canvas-button').trigger('click')
    expect(wrapper.findAll('.canvas-block')).toHaveLength(0)

    await wrapper.find('.load-draft-button').trigger('click')

    const placedBlocks = wrapper.findAll('.canvas-block')
    expect(placedBlocks).toHaveLength(1)
    expect(placedBlocks[0].text()).toContain('买入')
    expect(wrapper.find('.draft-status').text()).toContain('已从本机浏览器加载草稿')
  })

  it('saves the current strategy to the authenticated personal space', async () => {
    const authStore = useAuthStore()
    authStore.setSession({
      token: 'token-123',
      user: { id: 1, username: 'alice', email: 'alice@example.com', roles: ['user'] }
    })
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        id: 7,
        name: '未命名策略',
        description: null,
        strategy: {},
        backtestConfig: null,
        ownerId: 1,
        isPublic: false,
        createdAt: '2026-06-05T12:00:00',
        updatedAt: '2026-06-05T12:00:00'
      }
    })
    const wrapper = mount(BuilderView)
    await dropBlock(wrapper, 'buy', 260, 170)

    window.dispatchEvent(new CustomEvent('sts:builder-action', { detail: { action: 'save' } }))
    await flushPromises()

    expect(apiClient.post).toHaveBeenCalledWith('/strategies', {
      name: '未命名策略',
      description: null,
      strategy: expect.objectContaining({
        version: 1,
        nodes: expect.arrayContaining([expect.objectContaining({ type: 'buy' })])
      }),
      backtestConfig: expect.objectContaining({
        symbol: '000001.SZ',
        timeframe: '5m'
      })
    })
    expect(wrapper.find('.strategy-save-status').text()).toContain('已保存到个人空间')
  })

  it('loads a backtest strategy snapshot as a new editable strategy', async () => {
    const workspaceStore = useStrategyWorkspaceStore()
    workspaceStore.openBacktestSnapshot({
      name: '回测复盘：000001.SZ 5分钟',
      description: '来自回测记录 11',
      strategy: {
        version: 1,
        nodes: [
          {
            id: 'buy-1',
            type: 'buy',
            label: '买入',
            x: 72,
            y: 96,
            params: { sizePercent: '20', orderType: 'market' }
          },
          {
            id: 'stop-loss-1',
            type: 'stop-loss',
            label: '止损',
            x: 220,
            y: 96,
            params: { lossPercent: '3', sellPercent: '100' }
          }
        ],
        edges: [{ id: 'edge-1', from: 'buy-1', to: 'stop-loss-1' }],
        viewport: { x: 12, y: 24, scale: 1.2 }
      },
      backtestConfig: {
        market: 'A_SHARE',
        symbol: '000001.SZ',
        timeframe: '5m',
        startDate: '2026-01-01',
        endDate: '2026-03-01',
        initialCash: 100000,
        simulationAccountId: 3
      },
      statusMessage: '已载入回测策略快照：000001.SZ'
    })
    const authStore = useAuthStore()
    authStore.setSession({
      token: 'token-123',
      user: { id: 1, username: 'alice', email: 'alice@example.com', roles: ['user'] }
    })
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        id: 12,
        name: '回测复盘：000001.SZ 5分钟',
        description: null,
        strategy: {},
        backtestConfig: null,
        ownerId: 1,
        isPublic: false,
        createdAt: '2026-06-06T12:00:00',
        updatedAt: '2026-06-06T12:00:00'
      }
    })
    expect(workspaceStore.pendingWorkspaceDraft?.source).toBe('backtest-snapshot')
    const wrapper = mount(BuilderView)
    await nextTick()

    expect(wrapper.findAll('.canvas-block')).toHaveLength(2)
    expect(wrapper.text()).toContain('买入')
    expect(wrapper.text()).toContain('止损')
    expect(wrapper.find('.strategy-save-status').text()).toContain('回测策略快照')
    expect(workspaceStore.pendingWorkspaceDraft).toBeNull()

    window.dispatchEvent(new CustomEvent('sts:builder-action', { detail: { action: 'save' } }))
    await flushPromises()

    expect(apiClient.post).toHaveBeenCalledWith('/strategies', {
      name: '回测复盘：000001.SZ 5分钟',
      description: null,
      strategy: expect.objectContaining({
        nodes: expect.arrayContaining([expect.objectContaining({ type: 'buy' })])
      }),
      backtestConfig: expect.objectContaining({
        symbol: '000001.SZ',
        timeframe: '5m',
        simulationAccountId: 3
      })
    })
    expect(apiClient.put).not.toHaveBeenCalled()
  })

  it('asks anonymous users to log in before saving to personal space', async () => {
    const wrapper = mount(BuilderView)
    await dropBlock(wrapper, 'buy', 260, 170)
    const authRequiredListener = vi.fn()
    window.addEventListener('sts:auth-required', authRequiredListener)

    window.dispatchEvent(new CustomEvent('sts:builder-action', { detail: { action: 'save' } }))
    await nextTick()

    expect(apiClient.post).not.toHaveBeenCalled()
    expect(wrapper.find('.strategy-save-status').text()).toContain('请先登录')
    expect(authRequiredListener).toHaveBeenCalledOnce()

    window.removeEventListener('sts:auth-required', authRequiredListener)
  })

  it('keeps publishing separate from custom block creation', async () => {
    const authStore = useAuthStore()
    authStore.setSession({
      token: 'token-123',
      user: { id: 1, username: 'alice', email: 'alice@example.com', roles: ['user'] }
    })
    const wrapper = mount(BuilderView)
    await dropBlock(wrapper, 'buy', 260, 170)

    await openReviewModal('publish')

    expect(wrapper.find('.strategy-review-modal').text()).toContain('发布前检查')
    expect(wrapper.find('.review-primary-button').text()).toContain('确认发布')

    await wrapper.find('.review-primary-button').trigger('click')

    expect(apiClient.post).not.toHaveBeenCalledWith('/custom-blocks', expect.anything())
    expect(wrapper.find('.draft-status').text()).toContain('发布接口待接入')
  })

  it('creates private custom block templates from the block library', async () => {
    const authStore = useAuthStore()
    authStore.setSession({
      token: 'token-123',
      user: { id: 1, username: 'alice', email: 'alice@example.com', roles: ['user'] }
    })
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        id: 21,
        ownerId: 1,
        name: '突破买入模板',
        description: '把当前画布保存成模板',
        category: '动作',
        tags: ['突破', '买入'],
        template: {},
        reviewStatus: 'private',
        createdAt: '2026-06-06T11:00:00',
        updatedAt: '2026-06-06T11:00:00'
      }
    })
    const wrapper = mount(BuilderView)
    mockCanvasRect(wrapper)
    await dropBlock(wrapper, 'buy', 260, 170)

    await wrapper.find('.custom-block-create-button').trigger('click')
    await wrapper.find('.custom-block-name-input').setValue('突破买入模板')
    await wrapper.find('.custom-block-category-input').setValue('动作')
    await wrapper.find('.custom-block-description-input').setValue('把当前画布保存成模板')
    await wrapper.find('.custom-block-tags-input').setValue('突破, 买入')
    await wrapper.find('.custom-block-save-button').trigger('click')
    await flushPromises()

    expect(apiClient.post).toHaveBeenCalledWith('/custom-blocks', {
      name: '突破买入模板',
      description: '把当前画布保存成模板',
      category: '动作',
      tags: ['突破', '买入'],
      template: expect.objectContaining({
        version: 1,
        nodes: expect.arrayContaining([expect.objectContaining({ type: 'buy' })])
      })
    })
    expect(wrapper.find('.custom-block-status').text()).toContain('已保存到我的积木')
  })

  it('shows a clear message when a custom block name already exists', async () => {
    const authStore = useAuthStore()
    authStore.setSession({
      token: 'token-123',
      user: { id: 1, username: 'alice', email: 'alice@example.com', roles: ['user'] }
    })
    vi.mocked(apiClient.post).mockRejectedValueOnce({ response: { status: 409 } })
    const wrapper = mount(BuilderView)
    mockCanvasRect(wrapper)
    await dropBlock(wrapper, 'buy', 260, 170)

    await wrapper.find('.custom-block-create-button').trigger('click')
    await wrapper.find('.custom-block-name-input').setValue('重复模板')
    await wrapper.find('.custom-block-save-button').trigger('click')
    await flushPromises()

    expect(wrapper.find('.custom-block-status').text()).toContain('已存在同名积木')
  })

  it('validates whether the strategy draft can run', async () => {
    const wrapper = mount(BuilderView)
    mockCanvasRect(wrapper)
    await openReviewModal()

    expect(wrapper.find('.validation-summary').text()).toContain('需完善')
    expect(wrapper.find('.validation-issues').text()).toContain('请至少放置一个积木')

    await dropBlock(wrapper, 'buy', 260, 170)

    expect(wrapper.find('.validation-summary').text()).toContain('可运行')
    expect(wrapper.find('.validation-empty').text()).toContain('基础规则已通过')

    await wrapper.find('.canvas-block').trigger('contextmenu', { clientX: 260, clientY: 170 })
    await wrapper.find('[data-param-key="sizePercent"]').setValue('')

    expect(wrapper.find('.validation-summary').text()).toContain('需完善')
    expect(wrapper.find('.validation-issues').text()).toContain('买入 的 买入仓位 不能为空')
  })

  it('renders and updates the backtest configuration JSON', async () => {
    const wrapper = mount(BuilderView)
    mockCanvasRect(wrapper)
    await dropBlock(wrapper, 'buy', 260, 170)
    await openReviewModal()

    const initialConfig = JSON.parse(wrapper.find('.backtest-config-preview').text())
    expect(initialConfig).toMatchObject({
      market: 'A_SHARE',
      symbol: '000001.SZ',
      timeframe: '5m',
      startDate: '2026-01-01',
      endDate: '2026-03-01',
      initialCash: 100000
    })
    expect(wrapper.find('.backtest-summary').text()).toContain('回测就绪')

    await wrapper.find('[data-backtest-key="market"]').setValue('US_STOCK')
    await wrapper.find('[data-backtest-key="symbol"]').setValue('AAPL')
    await wrapper.find('[data-backtest-key="timeframe"]').setValue('1m')
    await wrapper.find('[data-backtest-key="startDate"]').setValue('2026-06-01')
    await wrapper.find('[data-backtest-key="endDate"]').setValue('2026-06-05')
    await wrapper.find('[data-backtest-key="initialCash"]').setValue('250000')

    const updatedConfig = JSON.parse(wrapper.find('.backtest-config-preview').text())
    expect(updatedConfig).toMatchObject({
      market: 'US_STOCK',
      symbol: 'AAPL',
      timeframe: '1m',
      startDate: '2026-06-01',
      endDate: '2026-06-05',
      initialCash: 250000
    })
  })

  it('validates backtest settings before running', async () => {
    const wrapper = mount(BuilderView)
    mockCanvasRect(wrapper)
    await openReviewModal()

    expect(wrapper.find('.backtest-summary').text()).toContain('需完善')
    expect(wrapper.find('.backtest-issues').text()).toContain('策略校验通过后才能运行回测')

    await dropBlock(wrapper, 'buy', 260, 170)
    expect(wrapper.find('.backtest-summary').text()).toContain('回测就绪')

    await wrapper.find('[data-backtest-key="symbol"]').setValue('')
    expect(wrapper.find('.backtest-issues').text()).toContain('股票代码不能为空')

    await wrapper.find('[data-backtest-key="symbol"]').setValue('000001.SZ')
    await wrapper.find('[data-backtest-key="timeframe"]').setValue('1m')
    await wrapper.find('[data-backtest-key="startDate"]').setValue('2026-06-01')
    await wrapper.find('[data-backtest-key="endDate"]').setValue('2026-06-12')

    expect(wrapper.find('.backtest-issues').text()).toContain('1分钟K线最多选择7天范围')
  })

  it('runs a backtest and renders the returned result summary', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        runId: 'mock-run-1',
        status: 'COMPLETED',
        summary: {
          totalReturnPercent: 7.3,
          maxDrawdownPercent: 2.8,
          winRatePercent: 66.7,
          endingEquity: 107300,
          tradeCount: 3
        },
        config: {
          market: 'A_SHARE',
          symbol: '000001.SZ',
          timeframe: '5m',
          startDate: '2026-01-01',
          endDate: '2026-03-01',
          initialCash: 100000
        },
        trades: [
          {
            time: '2026-01-05 10:30',
            side: 'BUY',
            price: 10.2,
            quantity: 1900,
            reason: '买入积木触发'
          }
        ],
        events: [
          {
            time: '2026-01-05 10:35',
            eventType: 'BLOCKED_ORDER',
            side: 'SELL',
            price: 10.6,
            quantity: 1900,
            reason: 'A股 T+1 规则限制，当日买入持仓不可卖出',
            rule: 'T+1'
          }
        ],
        timeline: [
          {
            id: 'trade-filled-0',
            time: '2026-01-05 10:30',
            eventType: 'TRADE_FILLED',
            title: '买入成交',
            description: '买入积木触发',
            severity: 'success',
            side: 'BUY',
            price: 10.2,
            quantity: 1900,
            rule: null,
            nodeId: 'buy-1',
            nodeType: 'buy',
            nodeLabel: '买入',
            details: {}
          },
          {
            id: 'order-blocked-1',
            time: '2026-01-05 10:35',
            eventType: 'ORDER_BLOCKED',
            title: '卖出信号被拦截',
            description: 'A股 T+1 规则限制，当日买入持仓不可卖出',
            severity: 'warning',
            side: 'SELL',
            price: 10.6,
            quantity: 1900,
            rule: 'T+1',
            nodeId: 'take-profit-1',
            nodeType: 'take-profit',
            nodeLabel: '止盈',
            details: {}
          }
        ],
        equityCurve: [
          { time: '2026-01-01', equity: 100000 },
          { time: '2026-03-01', equity: 107300 }
        ]
      }
    })
    const wrapper = mount(BuilderView)
    mockCanvasRect(wrapper)
    await dropBlock(wrapper, 'buy', 260, 170)
    await openReviewModal()

    await wrapper.find('.review-primary-button').trigger('click')
    await flushPromises()

    expect(apiClient.post).toHaveBeenCalledWith('/backtests/run', {
      strategy: expect.objectContaining({
        version: 1,
        nodes: expect.arrayContaining([
          expect.objectContaining({
            type: 'buy'
          })
        ])
      }),
      config: expect.objectContaining({
        symbol: '000001.SZ',
        timeframe: '5m',
        initialCash: 100000
      })
    })
    expect(wrapper.find('.backtest-result-card').text()).toContain('总收益率')
    expect(wrapper.find('.backtest-result-card').text()).toContain('7.3%')
    expect(wrapper.find('.backtest-result-card').text()).toContain('最大回撤')
    expect(wrapper.find('.backtest-result-card').text()).toContain('2.8%')
    expect(wrapper.find('.backtest-trades').text()).toContain('BUY')
    expect(wrapper.find('.backtest-trades').text()).toContain('买入积木触发')
    expect(wrapper.find('.backtest-events').text()).toContain('规则提示')
    expect(wrapper.find('.backtest-events').text()).toContain('A股 T+1 规则限制')
    expect(wrapper.find('.backtest-timeline').text()).toContain('策略执行时间线')
    expect(wrapper.find('.backtest-timeline').text()).toContain('买入成交')
    expect(wrapper.find('.backtest-timeline').text()).toContain('卖出信号被拦截')
    expect(wrapper.find('.backtest-timeline').text()).toContain('止盈')
  })

  it('links authenticated backtest runs to the saved personal-space record list', async () => {
    const authStore = useAuthStore()
    authStore.setSession({
      token: 'token-123',
      user: { id: 1, username: 'alice', email: 'alice@example.com', roles: ['user'] }
    })
    vi.mocked(apiClient.get).mockImplementation((url) => {
      if (url === '/simulation-accounts' || url === '/custom-blocks') {
        return Promise.resolve({
          data: {
            items: [],
            total: 0,
            page: 1,
            pageSize: 50
          }
        })
      }
      return Promise.reject(new Error(`Unexpected GET ${url}`))
    })
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        runId: 'mock-run-saved',
        status: 'COMPLETED',
        summary: {
          totalReturnPercent: 5.2,
          maxDrawdownPercent: 1.4,
          winRatePercent: 60,
          endingEquity: 105200,
          tradeCount: 2
        },
        config: {
          market: 'A_SHARE',
          symbol: '000001.SZ',
          timeframe: '5m',
          startDate: '2026-01-01',
          endDate: '2026-03-01',
          initialCash: 100000
        },
        trades: [],
        events: [],
        timeline: [],
        equityCurve: []
      }
    })
    const wrapper = mount(BuilderView)
    mockCanvasRect(wrapper)
    await dropBlock(wrapper, 'buy', 260, 170)
    await openReviewModal()
    await flushPromises()

    await wrapper.find('.review-primary-button').trigger('click')
    await flushPromises()

    expect(wrapper.find('.backtest-persist-status').text()).toContain('已保存到个人空间')
    expect(wrapper.find('.backtest-space-button').exists()).toBe(true)

    await wrapper.find('.backtest-space-button').trigger('click')

    expect(builderPushMock).toHaveBeenCalledWith({
      path: '/space',
      query: { tab: 'backtests' }
    })
  })

  it('uses a selected simulation account when running a backtest', async () => {
    const authStore = useAuthStore()
    authStore.setSession({
      token: 'token-123',
      user: {
        id: 1,
        username: 'alice',
        email: 'alice@example.com',
        roles: ['user']
      }
    })
    vi.mocked(apiClient.get).mockImplementation((url) => {
      if (url === '/custom-blocks') {
        return Promise.resolve({
          data: {
            items: [],
            total: 0,
            page: 1,
            pageSize: 50
          }
        })
      }
      if (url === '/simulation-accounts') {
        return Promise.resolve({
          data: {
            items: [
              {
                id: 3,
                ownerId: 1,
                name: '美股一分钟账户',
                description: '美股短线测试',
                market: 'US_STOCK',
                initialCash: 50000,
                createdAt: '2026-06-06T09:00:00',
                updatedAt: '2026-06-06T09:00:00'
              }
            ],
            total: 1,
            page: 1,
            pageSize: 50
          }
        })
      }
      return Promise.reject(new Error(`Unexpected GET ${url}`))
    })
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        runId: 'mock-run-account',
        status: 'COMPLETED',
        summary: {
          totalReturnPercent: 4.2,
          maxDrawdownPercent: 1.8,
          winRatePercent: 50,
          endingEquity: 52100,
          tradeCount: 2
        },
        config: {
          market: 'US_STOCK',
          symbol: 'AAPL',
          timeframe: '5m',
          startDate: '2026-01-01',
          endDate: '2026-03-01',
          initialCash: 50000,
          simulationAccountId: 3
        },
        trades: [],
        events: [],
        timeline: [],
        equityCurve: []
      }
    })
    const wrapper = mount(BuilderView)
    mockCanvasRect(wrapper)
    await dropBlock(wrapper, 'buy', 260, 170)
    await openReviewModal()
    await flushPromises()

    expect(apiClient.get).toHaveBeenCalledWith('/simulation-accounts', {
      params: { page: 1, pageSize: 50 }
    })
    expect(wrapper.text()).toContain('美股一分钟账户')

    await wrapper.find('[data-backtest-key="simulationAccountId"]').setValue('3')
    await wrapper.find('[data-backtest-key="symbol"]').setValue('AAPL')

    const selectedConfig = JSON.parse(wrapper.find('.backtest-config-preview').text())
    expect(selectedConfig).toMatchObject({
      market: 'US_STOCK',
      symbol: 'AAPL',
      initialCash: 50000,
      simulationAccountId: 3
    })
    expect((wrapper.find('[data-backtest-key="market"]').element as HTMLSelectElement).disabled).toBe(
      true
    )
    expect(
      (wrapper.find('[data-backtest-key="initialCash"]').element as HTMLInputElement).disabled
    ).toBe(true)

    await wrapper.find('.review-primary-button').trigger('click')
    await flushPromises()

    expect(apiClient.post).toHaveBeenCalledWith('/backtests/run', {
      strategy: expect.any(Object),
      config: expect.objectContaining({
        market: 'US_STOCK',
        symbol: 'AAPL',
        initialCash: 50000,
        simulationAccountId: 3
      })
    })
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
    await wrapper.find('.connection-path').trigger('contextmenu', { clientX: 360, clientY: 220 })

    expect(wrapper.findAll('.canvas-block')).toHaveLength(2)
    expect(wrapper.find('.connection-path').exists()).toBe(true)
    expect(wrapper.find('.context-menu').exists()).toBe(true)
    expect(wrapper.find('.block-inspector').exists()).toBe(true)

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

  it('does not zoom the canvas when scrolling the floating block library', async () => {
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

    wrapper.find('.floating-block-library').element.dispatchEvent(
      new WheelEvent('wheel', { clientX: 760, clientY: 160, deltaY: 100, bubbles: true })
    )
    await nextTick()

    expect(wrapper.find('.canvas-controls span').text()).toBe('100%')
    expect(wrapper.find('.canvas-world').attributes('style')).toContain('scale(1)')
  })
})
