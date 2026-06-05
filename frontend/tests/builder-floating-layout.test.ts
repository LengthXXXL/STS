import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const css = readFileSync('src/styles/base.css', 'utf8')

function ruleBody(selector: string) {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = css.match(new RegExp(`${escapedSelector}\\s*\\{([^}]*)\\}`))
  return match?.[1] ?? ''
}

describe('builder floating layout styles', () => {
  it('keeps the canvas free of a persistent strategy preview panel', () => {
    const library = ruleBody('.floating-block-library')
    const canvasControls = ruleBody('.canvas-controls')

    expect(library).toContain('top: 20px')
    expect(library).toContain('right: 20px')
    expect(canvasControls).toContain('left: 20px')
    expect(canvasControls).toContain('bottom: 20px')
    expect(ruleBody('.strategy-draft-panel')).toBe('')
    expect(ruleBody('.strategy-review-backdrop')).toContain('position: fixed')
  })

  it('renders the collapsed block library as a narrow vertical tab', () => {
    const collapsedLibrary = ruleBody('.floating-block-library.is-collapsed')
    const collapsedHeader = ruleBody('.floating-block-library.is-collapsed .block-library-header')
    const collapsedTitle = ruleBody('.floating-block-library.is-collapsed .block-library-header h2')
    const collapsedDots = ruleBody(
      '.floating-block-library.is-collapsed .block-library-header-actions span'
    )
    const toggle = ruleBody('.block-library-collapse-toggle')
    const toggleIcon = ruleBody('.block-library-collapse-toggle::before')

    expect(collapsedLibrary).toContain('width: 52px')
    expect(collapsedLibrary).toContain('padding: 12px 8px')
    expect(collapsedHeader).toContain('flex-direction: column')
    expect(collapsedHeader).toContain('justify-content: center')
    expect(collapsedTitle).toContain('writing-mode: vertical-rl')
    expect(collapsedTitle).toContain('white-space: nowrap')
    expect(collapsedDots).toContain('display: none')
    expect(toggle).toContain('display: inline-flex')
    expect(toggle).toContain('align-items: center')
    expect(toggle).toContain('justify-content: center')
    expect(toggleIcon).toContain('content: ""')
  })
})
