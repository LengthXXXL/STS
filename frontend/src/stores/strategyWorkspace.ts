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

export const useStrategyWorkspaceStore = defineStore('strategyWorkspace', () => {
  const pendingStrategy = ref<SavedStrategy | null>(null)

  function openStrategy(strategy: SavedStrategy) {
    pendingStrategy.value = strategy
  }

  function consumePendingStrategy() {
    const strategy = pendingStrategy.value
    pendingStrategy.value = null
    return strategy
  }

  return {
    pendingStrategy,
    openStrategy,
    consumePendingStrategy
  }
})
