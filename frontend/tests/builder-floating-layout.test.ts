import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const css = readFileSync('src/styles/base.css', 'utf8')

function ruleBody(selector: string) {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = css.match(new RegExp(`${escapedSelector}\\s*\\{([^}]*)\\}`))
  return match?.[1] ?? ''
}

describe('builder floating layout styles', () => {
  it('distributes the main floating panels instead of stacking them on the right edge', () => {
    const library = ruleBody('.floating-block-library')
    const strategyPanel = ruleBody('.strategy-draft-panel')
    const canvasControls = ruleBody('.canvas-controls')

    expect(library).toContain('top: 20px')
    expect(library).toContain('right: 20px')
    expect(strategyPanel).toContain('left: 20px')
    expect(strategyPanel).toContain('bottom: 84px')
    expect(strategyPanel).not.toContain('right: 20px')
    expect(canvasControls).toContain('left: 20px')
    expect(canvasControls).toContain('bottom: 20px')
  })
})
