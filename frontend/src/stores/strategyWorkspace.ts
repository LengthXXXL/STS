import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface StrategyNodeDraft {
  id: string
  type: string
  label: string
  x: number
  y: number
  params: Record<string, string>
}

export interface StrategyEdgeDraft {
  id: string
  from: string
  to: string
}

export interface StrategyViewportDraft {
  x: number
  y: number
  scale: number
}

export interface StrategyDraftPayload {
  version: 1
  nodes: StrategyNodeDraft[]
  edges: StrategyEdgeDraft[]
  viewport: StrategyViewportDraft
}

export interface BacktestConfigPayload {
  market: 'A_SHARE' | 'US_STOCK'
  symbol: string
  timeframe: '5m' | '1m'
  startDate: string
  endDate: string
  initialCash: number
  simulationAccountId?: number
}

export interface SavedStrategy {
  id: number
  name: string
  description: string | null
  ownerId: number
  isPublic: boolean
  createdAt: string
  updatedAt: string
  strategy: StrategyDraftPayload
  backtestConfig: BacktestConfigPayload | null
}

export interface WorkspaceStrategyDraft {
  source: 'saved-strategy' | 'backtest-snapshot' | 'custom-block-template'
  name: string
  description: string | null
  strategy: StrategyDraftPayload
  backtestConfig: BacktestConfigPayload | null
  savedStrategyId?: number | null
  statusMessage: string
}

export interface CustomBlockWorkspaceTemplate {
  name: string
  description: string | null
  template: StrategyDraftPayload
}

export const useStrategyWorkspaceStore = defineStore('strategyWorkspace', () => {
  const pendingStrategy = ref<SavedStrategy | null>(null)
  const pendingWorkspaceDraft = ref<WorkspaceStrategyDraft | null>(null)

  function openStrategy(strategy: SavedStrategy) {
    pendingStrategy.value = strategy
    pendingWorkspaceDraft.value = {
      source: 'saved-strategy',
      name: strategy.name,
      description: strategy.description,
      strategy: strategy.strategy,
      backtestConfig: strategy.backtestConfig,
      savedStrategyId: strategy.id,
      statusMessage: `已打开个人空间策略：${strategy.name}`
    }
  }

  function openBacktestSnapshot(draft: Omit<WorkspaceStrategyDraft, 'source'>) {
    pendingStrategy.value = null
    pendingWorkspaceDraft.value = {
      ...draft,
      source: 'backtest-snapshot',
      savedStrategyId: null
    }
  }

  function openCustomBlockTemplate(block: CustomBlockWorkspaceTemplate) {
    pendingStrategy.value = null
    pendingWorkspaceDraft.value = {
      source: 'custom-block-template',
      name: block.name,
      description: block.description,
      strategy: block.template,
      backtestConfig: null,
      savedStrategyId: null,
      statusMessage: `已载入我的积木：${block.name}`
    }
  }

  function consumePendingWorkspaceDraft() {
    const draft = pendingWorkspaceDraft.value
    pendingWorkspaceDraft.value = null
    pendingStrategy.value = null
    return draft
  }

  function consumePendingStrategy() {
    const strategy = pendingStrategy.value
    pendingStrategy.value = null
    if (pendingWorkspaceDraft.value?.source === 'saved-strategy') {
      pendingWorkspaceDraft.value = null
    }
    return strategy
  }

  return {
    pendingStrategy,
    pendingWorkspaceDraft,
    openStrategy,
    openBacktestSnapshot,
    openCustomBlockTemplate,
    consumePendingWorkspaceDraft,
    consumePendingStrategy
  }
})
