<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiClient } from '../api/http'
import BacktestResultVisualization from '../components/BacktestResultVisualization.vue'
import { useAuthStore } from '../stores/auth'
import {
  useStrategyWorkspaceStore,
  type BacktestConfigPayload,
  type SavedStrategy,
  type StrategyDraftPayload
} from '../stores/strategyWorkspace'

type SpaceTab =
  | 'overview'
  | 'strategies'
  | 'custom-blocks'
  | 'accounts'
  | 'backtests'
  | 'files'
  | 'forum'

type ForumReviewStatus = 'pending_review' | 'approved' | 'rejected'
type ForumContentTab = 'posts' | 'comments'

interface StrategyListResponse {
  items: SavedStrategy[]
  total: number
  page: number
  pageSize: number
}

interface BacktestListItem {
  id: number
  runId: string
  status: string
  market: 'A_SHARE' | 'US_STOCK'
  symbol: string
  timeframe: '5m' | '1m'
  startDate: string
  endDate: string
  totalReturnPercent: number
  maxDrawdownPercent: number
  winRatePercent: number
  endingEquity: number
  tradeCount: number
  simulationAccountId?: number | null
  simulationAccountName?: string | null
  createdAt: string
}

interface BacktestListResponse {
  items: BacktestListItem[]
  total: number
  page: number
  pageSize: number
}

interface SimulationAccount {
  id: number
  ownerId: number
  name: string
  description: string | null
  market: 'A_SHARE' | 'US_STOCK'
  initialCash: number
  createdAt: string
  updatedAt: string
}

interface SimulationAccountListResponse {
  items: SimulationAccount[]
  total: number
  page: number
  pageSize: number
}

interface MarketSession {
  label: string
  start: string
  end: string
}

interface MarketRule {
  market: SimulationAccount['market']
  marketLabel: string
  currency: string
  timezone: string
  settlementCycle: string
  buyLotSize: number
  sellLotSize: number
  minOrderShares: number
  supportsIntradayRoundTrip: boolean
  priceLimitPercent: number | null
  sessions: MarketSession[]
  notes: string[]
}

interface MarketRuleListResponse {
  items: MarketRule[]
}

interface CustomBlock {
  id: number
  ownerId: number
  name: string
  description: string | null
  category: string
  tags: string[]
  template: StrategyDraftPayload
  reviewStatus: 'private' | 'pending_review' | 'approved' | 'rejected'
  createdAt: string
  updatedAt: string
}

interface CustomBlockListResponse {
  items: CustomBlock[]
  total: number
  page: number
  pageSize: number
}

interface ForumPostItem {
  id: number
  authorId: number
  authorName: string
  title: string
  content: string
  topic: string
  sharedBlockId: number | null
  reviewStatus: ForumReviewStatus
  reviewReason: string | null
  commentCount: number
  createdAt: string
  updatedAt: string
}

interface ForumPostListResponse {
  items: ForumPostItem[]
  total: number
  page: number
  pageSize: number
}

interface ForumCommentItem {
  id: number
  postId: number
  postTitle: string
  authorId: number
  authorName: string
  content: string
  reviewStatus: ForumReviewStatus
  reviewReason: string | null
  createdAt: string
  updatedAt: string
}

interface ForumCommentListResponse {
  items: ForumCommentItem[]
  total: number
  page: number
  pageSize: number
}

interface UploadedFileItem {
  id: number
  ownerId: number
  originalName: string
  contentType: string
  size: number
  businessType: string
  businessId: number | null
  visibility: string
  createdAt: string
  downloadUrl: string
}

interface UploadedFileListResponse {
  items: UploadedFileItem[]
  total: number
  page: number
  pageSize: number
}

interface BacktestTrade {
  time: string
  side: 'BUY' | 'SELL'
  price: number
  quantity: number
  reason: string
}

interface BacktestEvent {
  time: string
  eventType: 'BLOCKED_ORDER'
  side: BacktestTrade['side']
  price: number
  quantity: number
  reason: string
  rule: string
}

interface BacktestTimelineItem {
  id: string
  time: string
  eventType: 'TRADE_FILLED' | 'ORDER_BLOCKED' | 'COOLDOWN_STARTED' | 'POSITION_CLOSED'
  title: string
  description: string
  severity: 'info' | 'success' | 'warning' | 'danger'
  side?: BacktestTrade['side'] | null
  price?: number | null
  quantity?: number | null
  rule?: string | null
  nodeId?: string | null
  nodeType?: string | null
  nodeLabel?: string | null
  details: Record<string, string | number | boolean>
}

interface EquityPoint {
  time: string
  equity: number
}

interface SnapshotField {
  label: string
  value: string
}

interface StrategyBlockSummary {
  label: string
  count: number
}

interface CustomBlockForm {
  name: string
  description: string
  category: string
  tags: string
}

interface BacktestDetail extends BacktestListItem {
  strategy: StrategyDraftPayload
  config: BacktestConfigPayload & {
    simulationAccountId?: number | null
  }
  summary: {
    totalReturnPercent: number
    maxDrawdownPercent: number
    winRatePercent: number
    endingEquity: number
    tradeCount: number
  }
  trades: BacktestTrade[]
  events: BacktestEvent[]
  timeline?: BacktestTimelineItem[]
  equityCurve: EquityPoint[]
}

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const workspaceStore = useStrategyWorkspaceStore()
const activeTab = ref<SpaceTab>(spaceTabFromQuery(route.query.tab))
const strategies = ref<SavedStrategy[]>([])
const customBlocks = ref<CustomBlock[]>([])
const accounts = ref<SimulationAccount[]>([])
const marketRules = ref<MarketRule[]>([])
const backtests = ref<BacktestListItem[]>([])
const forumPosts = ref<ForumPostItem[]>([])
const forumComments = ref<ForumCommentItem[]>([])
const uploadedFiles = ref<UploadedFileItem[]>([])
const selectedBacktest = ref<BacktestDetail | null>(null)
const strategyKeyword = ref('')
const customBlockKeyword = ref('')
const accountKeyword = ref('')
const backtestKeyword = ref('')
const fileKeyword = ref('')
const activeForumTab = ref<ForumContentTab>('posts')
const strategyPage = ref(1)
const customBlockPage = ref(1)
const accountPage = ref(1)
const backtestPage = ref(1)
const filePage = ref(1)
const forumPostPage = ref(1)
const forumCommentPage = ref(1)
const pageSize = 10
const strategyTotal = ref(0)
const customBlockTotal = ref(0)
const accountTotal = ref(0)
const backtestTotal = ref(0)
const fileTotal = ref(0)
const forumPostTotal = ref(0)
const forumCommentTotal = ref(0)
const strategyLoading = ref(false)
const customBlockLoading = ref(false)
const accountLoading = ref(false)
const backtestLoading = ref(false)
const fileLoading = ref(false)
const forumPostLoading = ref(false)
const forumCommentLoading = ref(false)
const backtestDetailLoading = ref(false)
const strategyError = ref('')
const strategyActionError = ref('')
const strategyActionMessage = ref('')
const customBlockError = ref('')
const customBlockActionError = ref('')
const customBlockActionMessage = ref('')
const accountError = ref('')
const marketRuleError = ref('')
const backtestError = ref('')
const fileError = ref('')
const fileActionError = ref('')
const fileActionMessage = ref('')
const forumPostError = ref('')
const forumCommentError = ref('')
const selectedUploadFile = ref<File | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const isUploadingFile = ref(false)
const editingStrategyId = ref<number | null>(null)
const strategyNameForm = ref('')
const isSavingStrategyName = ref(false)
const editingCustomBlockId = ref<number | null>(null)
const confirmingCustomBlockDeleteId = ref<number | null>(null)
const customBlockForm = ref<CustomBlockForm>({
  name: '',
  description: '',
  category: '',
  tags: ''
})
const editingAccountId = ref<number | null>(null)
const accountForm = ref({
  name: '',
  description: '',
  market: 'A_SHARE' as SimulationAccount['market'],
  initialCash: 100000
})
function spaceTabFromQuery(tab: unknown): SpaceTab {
  const value = Array.isArray(tab) ? tab[0] : tab
  if (
    value === 'overview' ||
    value === 'strategies' ||
    value === 'custom-blocks' ||
    value === 'accounts' ||
    value === 'backtests' ||
    value === 'files' ||
    value === 'forum'
  ) {
    return value
  }
  return 'overview'
}

const bestBacktest = computed(() =>
  backtests.value.reduce<BacktestListItem | null>((best, item) => {
    if (!best || item.totalReturnPercent > best.totalReturnPercent) {
      return item
    }
    return best
  }, null)
)

const lowestDrawdownBacktest = computed(() =>
  backtests.value.reduce<BacktestListItem | null>((best, item) => {
    if (!best || item.maxDrawdownPercent < best.maxDrawdownPercent) {
      return item
    }
    return best
  }, null)
)

const latestStrategy = computed(() => strategies.value[0] ?? null)
const latestCustomBlock = computed(() => customBlocks.value[0] ?? null)
const latestAccount = computed(() => accounts.value[0] ?? null)
const latestBacktest = computed(() => backtests.value[0] ?? null)
const latestForumPost = computed(() => forumPosts.value[0] ?? null)
const latestFile = computed(() => uploadedFiles.value[0] ?? null)
const forumContentTotal = computed(() => forumPostTotal.value + forumCommentTotal.value)
const strategyTotalPages = computed(() => Math.max(1, Math.ceil(strategyTotal.value / pageSize)))
const customBlockTotalPages = computed(() =>
  Math.max(1, Math.ceil(customBlockTotal.value / pageSize))
)
const accountTotalPages = computed(() => Math.max(1, Math.ceil(accountTotal.value / pageSize)))
const backtestTotalPages = computed(() => Math.max(1, Math.ceil(backtestTotal.value / pageSize)))
const fileTotalPages = computed(() => Math.max(1, Math.ceil(fileTotal.value / pageSize)))
const forumPostTotalPages = computed(() => Math.max(1, Math.ceil(forumPostTotal.value / pageSize)))
const forumCommentTotalPages = computed(() =>
  Math.max(1, Math.ceil(forumCommentTotal.value / pageSize))
)
const customBlockNameCounts = computed(() => {
  const counts = new Map<string, number>()
  customBlocks.value.forEach((block) => {
    const nameKey = normalizedCustomBlockName(block.name)
    counts.set(nameKey, (counts.get(nameKey) ?? 0) + 1)
  })
  return counts
})
const selectedMarketRule = computed(() =>
  marketRules.value.find((rule) => rule.market === accountForm.value.market)
)
const selectedBacktestSnapshotFields = computed<SnapshotField[]>(() => {
  const backtest = selectedBacktest.value
  if (!backtest) {
    return []
  }

  return [
    { label: '市场', value: formatMarket(backtest.config.market) },
    { label: '股票', value: backtest.config.symbol },
    { label: '周期', value: formatTimeframe(backtest.config.timeframe) },
    { label: '区间', value: `${backtest.config.startDate} 至 ${backtest.config.endDate}` },
    { label: '初始资金', value: formatAmount(backtest.config.initialCash) },
    { label: '模拟账户', value: backtest.simulationAccountName ?? '未绑定' }
  ]
})
const selectedStrategyBlockSummaries = computed<StrategyBlockSummary[]>(() =>
  summarizeStrategyBlocks(selectedBacktest.value?.strategy)
)

function summarizeStrategyBlocks(strategy: StrategyDraftPayload | undefined) {
  const nodes = strategy?.nodes ?? []
  const counts = nodes.reduce<Map<string, StrategyBlockSummary>>((summary, node) => {
    const label = node.label || node.type
    const current = summary.get(label) ?? { label, count: 0 }
    current.count += 1
    summary.set(label, current)
    return summary
  }, new Map())
  return Array.from(counts.values()).sort((left, right) => left.label.localeCompare(right.label))
}

async function loadStrategies() {
  strategyLoading.value = true
  strategyError.value = ''
  try {
    const response = await apiClient.get<StrategyListResponse>('/strategies', {
      params: {
        keyword: strategyKeyword.value.trim(),
        page: strategyPage.value,
        pageSize
      }
    })
    strategies.value = response.data.items
    strategyTotal.value = response.data.total
  } catch {
    strategyError.value = '策略列表加载失败，请确认已登录'
  } finally {
    strategyLoading.value = false
  }
}

async function searchStrategies() {
  strategyPage.value = 1
  await loadStrategies()
}

async function loadCustomBlocks() {
  customBlockLoading.value = true
  customBlockError.value = ''
  try {
    const response = await apiClient.get<CustomBlockListResponse>('/custom-blocks', {
      params: {
        keyword: customBlockKeyword.value.trim(),
        page: customBlockPage.value,
        pageSize
      }
    })
    customBlocks.value = response.data.items
    customBlockTotal.value = response.data.total
  } catch {
    customBlockError.value = '自定义积木加载失败，请确认已登录'
  } finally {
    customBlockLoading.value = false
  }
}

async function searchCustomBlocks() {
  customBlockPage.value = 1
  await loadCustomBlocks()
}

async function loadAccounts() {
  accountLoading.value = true
  accountError.value = ''
  try {
    const response = await apiClient.get<SimulationAccountListResponse>('/simulation-accounts', {
      params: {
        keyword: accountKeyword.value.trim(),
        page: accountPage.value,
        pageSize
      }
    })
    accounts.value = response.data.items
    accountTotal.value = response.data.total
  } catch {
    accountError.value = '模拟账户加载失败，请确认已登录'
  } finally {
    accountLoading.value = false
  }
}

async function loadMarketRules() {
  marketRuleError.value = ''
  try {
    const response = await apiClient.get<MarketRuleListResponse>('/market-rules')
    marketRules.value = response.data.items
  } catch {
    marketRuleError.value = '市场规则加载失败'
  }
}

async function searchAccounts() {
  accountPage.value = 1
  await loadAccounts()
}

async function loadBacktests() {
  backtestLoading.value = true
  backtestError.value = ''
  try {
    const response = await apiClient.get<BacktestListResponse>('/backtests', {
      params: {
        keyword: backtestKeyword.value.trim(),
        page: backtestPage.value,
        pageSize
      }
    })
    backtests.value = response.data.items
    backtestTotal.value = response.data.total
    if (selectedBacktest.value) {
      const stillVisible = response.data.items.some((item) => item.id === selectedBacktest.value?.id)
      if (!stillVisible) {
        selectedBacktest.value = null
      }
    }
  } catch {
    backtestError.value = '回测记录加载失败，请确认已登录'
  } finally {
    backtestLoading.value = false
  }
}

async function loadFiles() {
  fileLoading.value = true
  fileError.value = ''
  try {
    const response = await apiClient.get<UploadedFileListResponse>('/files', {
      params: {
        keyword: fileKeyword.value.trim(),
        page: filePage.value,
        pageSize
      }
    })
    uploadedFiles.value = response.data.items
    fileTotal.value = response.data.total
  } catch {
    fileError.value = '文件列表加载失败，请确认已登录'
  } finally {
    fileLoading.value = false
  }
}

async function loadForumPosts() {
  forumPostLoading.value = true
  forumPostError.value = ''
  try {
    const response = await apiClient.get<ForumPostListResponse>('/forum/my-posts', {
      params: {
        page: forumPostPage.value,
        pageSize
      }
    })
    forumPosts.value = response.data.items
    forumPostTotal.value = response.data.total
  } catch {
    forumPostError.value = '我的帖子加载失败，请确认已登录'
  } finally {
    forumPostLoading.value = false
  }
}

async function loadForumComments() {
  forumCommentLoading.value = true
  forumCommentError.value = ''
  try {
    const response = await apiClient.get<ForumCommentListResponse>('/forum/my-comments', {
      params: {
        page: forumCommentPage.value,
        pageSize
      }
    })
    forumComments.value = response.data.items
    forumCommentTotal.value = response.data.total
  } catch {
    forumCommentError.value = '我的评论加载失败，请确认已登录'
  } finally {
    forumCommentLoading.value = false
  }
}

async function loadSpaceData() {
  await Promise.all([
    loadStrategies(),
    loadCustomBlocks(),
    loadAccounts(),
    loadMarketRules(),
    loadBacktests(),
    loadFiles(),
    loadForumPosts(),
    loadForumComments()
  ])
}

async function searchBacktests() {
  backtestPage.value = 1
  selectedBacktest.value = null
  await loadBacktests()
}

async function searchFiles() {
  filePage.value = 1
  await loadFiles()
}

async function searchActiveTab() {
  if (activeTab.value === 'strategies') {
    await searchStrategies()
    return
  }
  if (activeTab.value === 'custom-blocks') {
    await searchCustomBlocks()
    return
  }
  if (activeTab.value === 'accounts') {
    await searchAccounts()
    return
  }
  if (activeTab.value === 'backtests') {
    await searchBacktests()
    return
  }
  if (activeTab.value === 'files') {
    await searchFiles()
  }
}

function openStrategy(strategy: SavedStrategy) {
  workspaceStore.openStrategy(strategy)
  void router.push('/')
}

function editStrategyName(strategy: SavedStrategy) {
  editingStrategyId.value = strategy.id
  strategyNameForm.value = strategy.name
  strategyActionError.value = ''
  strategyActionMessage.value = ''
}

function cancelStrategyRename() {
  editingStrategyId.value = null
  strategyNameForm.value = ''
  strategyActionError.value = ''
}

async function submitStrategyRename(strategy: SavedStrategy) {
  const name = strategyNameForm.value.trim()
  strategyActionError.value = ''
  strategyActionMessage.value = ''

  if (!name) {
    strategyActionError.value = '请填写策略名称'
    return
  }

  if (name.length > 80) {
    strategyActionError.value = '策略名称最多 80 个字符'
    return
  }

  if (isSavingStrategyName.value) {
    return
  }

  isSavingStrategyName.value = true
  try {
    await apiClient.put(`/strategies/${strategy.id}`, {
      name,
      description: strategy.description,
      strategy: strategy.strategy,
      backtestConfig: strategy.backtestConfig
    })
    editingStrategyId.value = null
    strategyNameForm.value = ''
    strategyActionMessage.value = `已重命名策略：${name}`
    await loadStrategies()
  } catch {
    strategyActionError.value = '策略重命名失败，请稍后重试'
  } finally {
    isSavingStrategyName.value = false
  }
}

function openCustomBlock(block: CustomBlock) {
  workspaceStore.openCustomBlockTemplate({
    name: block.name,
    description: block.description,
    template: block.template
  })
  void router.push('/')
}

function customBlockPublishLabel(block: CustomBlock) {
  if (block.reviewStatus === 'pending_review') {
    return '待审核'
  }
  if (block.reviewStatus === 'approved') {
    return '已公开'
  }
  if (block.reviewStatus === 'rejected') {
    return '重新发布'
  }
  return '发布'
}

function canPublishCustomBlock(block: CustomBlock) {
  return block.reviewStatus === 'private' || block.reviewStatus === 'rejected'
}

async function publishCustomBlock(block: CustomBlock) {
  customBlockActionError.value = ''
  customBlockActionMessage.value = ''
  if (!canPublishCustomBlock(block)) {
    customBlockActionError.value = '该积木已提交审核或已公开'
    return
  }

  try {
    const response = await apiClient.post<CustomBlock>(`/custom-blocks/${block.id}/publish`)
    const index = customBlocks.value.findIndex((item) => item.id === block.id)
    if (index >= 0) {
      customBlocks.value[index] = response.data
    }
    customBlockActionMessage.value = `已提交审核：${response.data.name}`
  } catch {
    customBlockActionError.value = '发布失败，请稍后重试'
  }
}

async function deleteStrategy(strategy: SavedStrategy) {
  if (editingStrategyId.value === strategy.id) {
    cancelStrategyRename()
  }
  await apiClient.delete(`/strategies/${strategy.id}`)
  await loadStrategies()
}

function editCustomBlock(block: CustomBlock) {
  editingCustomBlockId.value = block.id
  confirmingCustomBlockDeleteId.value = null
  customBlockActionError.value = ''
  customBlockActionMessage.value = ''
  customBlockForm.value = {
    name: block.name,
    description: block.description ?? '',
    category: block.category,
    tags: block.tags.join(', ')
  }
}

function cancelCustomBlockEdit() {
  editingCustomBlockId.value = null
  customBlockActionError.value = ''
  customBlockActionMessage.value = ''
}

function customBlockFormTags() {
  return customBlockForm.value.tags
    .split(/[，,]/)
    .map((tag) => tag.trim())
    .filter((tag, index, tags) => tag && tags.indexOf(tag) === index)
    .slice(0, 12)
}

function responseStatusFromError(error: unknown) {
  if (typeof error !== 'object' || error === null || !('response' in error)) {
    return null
  }

  return (error as { response?: { status?: number } }).response?.status ?? null
}

function responseDetailFromError(error: unknown) {
  if (typeof error !== 'object' || error === null || !('response' in error)) {
    return null
  }

  const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
  return typeof detail === 'string' ? detail : null
}

function handleFileSelection(event: Event) {
  const input = event.target as HTMLInputElement
  selectedUploadFile.value = input.files?.[0] ?? null
  fileActionError.value = ''
  fileActionMessage.value = ''
}

async function uploadSelectedFile() {
  fileActionError.value = ''
  fileActionMessage.value = ''

  if (!selectedUploadFile.value) {
    fileActionError.value = '请先选择要上传的文件'
    return
  }

  if (isUploadingFile.value) {
    return
  }

  isUploadingFile.value = true
  const formData = new FormData()
  formData.append('file', selectedUploadFile.value)
  formData.append('businessType', 'general')
  formData.append('visibility', 'private')

  try {
    await apiClient.post<UploadedFileItem>('/files/upload', formData)
    fileActionMessage.value = `已上传文件：${selectedUploadFile.value.name}`
    selectedUploadFile.value = null
    if (fileInputRef.value) {
      fileInputRef.value.value = ''
    }
    await loadFiles()
  } catch (error) {
    fileActionError.value = responseDetailFromError(error) ?? '文件上传失败，请稍后重试'
  } finally {
    isUploadingFile.value = false
  }
}

async function downloadFile(file: UploadedFileItem) {
  fileActionError.value = ''
  fileActionMessage.value = ''

  try {
    const response = await apiClient.get<Blob>(`/files/${file.id}/download`, {
      responseType: 'blob'
    })
    const blob = response.data instanceof Blob
      ? response.data
      : new Blob([response.data], { type: file.contentType })
    const objectUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = objectUrl
    link.download = file.originalName
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(objectUrl)
  } catch {
    fileActionError.value = '文件下载失败，请稍后重试'
  }
}

async function deleteFile(file: UploadedFileItem) {
  fileActionError.value = ''
  fileActionMessage.value = ''

  try {
    await apiClient.delete(`/files/${file.id}`)
    fileActionMessage.value = `已删除文件：${file.originalName}`
    await loadFiles()
  } catch {
    fileActionError.value = '文件删除失败，请稍后重试'
  }
}

async function submitCustomBlock(block: CustomBlock) {
  const name = customBlockForm.value.name.trim()
  const category = customBlockForm.value.category.trim()

  customBlockActionMessage.value = ''
  customBlockActionError.value = ''

  if (!name) {
    customBlockActionError.value = '请填写积木名称'
    return
  }

  if (!category) {
    customBlockActionError.value = '请填写积木分类'
    return
  }

  try {
    await apiClient.put(`/custom-blocks/${block.id}`, {
      name,
      description: customBlockForm.value.description.trim() || null,
      category,
      tags: customBlockFormTags(),
      template: block.template
    })
    editingCustomBlockId.value = null
    customBlockActionMessage.value = `已更新自定义积木：${name}`
    await loadCustomBlocks()
  } catch (error) {
    customBlockActionError.value =
      responseStatusFromError(error) === 409
        ? '已存在同名积木，请换一个名称'
        : '自定义积木更新失败，请稍后重试'
  }
}

function requestDeleteCustomBlock(block: CustomBlock) {
  confirmingCustomBlockDeleteId.value = block.id
  editingCustomBlockId.value = null
  customBlockActionError.value = ''
  customBlockActionMessage.value = ''
}

function cancelDeleteCustomBlock() {
  confirmingCustomBlockDeleteId.value = null
}

async function confirmDeleteCustomBlock(block: CustomBlock) {
  await apiClient.delete(`/custom-blocks/${block.id}`)
  confirmingCustomBlockDeleteId.value = null
  if (editingCustomBlockId.value === block.id) {
    cancelCustomBlockEdit()
  }
  await loadCustomBlocks()
}

function resetAccountForm() {
  editingAccountId.value = null
  accountForm.value = {
    name: '',
    description: '',
    market: 'A_SHARE',
    initialCash: 100000
  }
}

async function submitAccount() {
  const payload = {
    name: accountForm.value.name.trim(),
    description: accountForm.value.description.trim() || null,
    market: accountForm.value.market,
    initialCash: Number(accountForm.value.initialCash)
  }

  if (editingAccountId.value) {
    await apiClient.put(`/simulation-accounts/${editingAccountId.value}`, payload)
  } else {
    await apiClient.post('/simulation-accounts', payload)
  }
  await loadAccounts()
  resetAccountForm()
}

function editAccount(account: SimulationAccount) {
  editingAccountId.value = account.id
  accountForm.value = {
    name: account.name,
    description: account.description ?? '',
    market: account.market,
    initialCash: account.initialCash
  }
}

async function deleteAccount(account: SimulationAccount) {
  await apiClient.delete(`/simulation-accounts/${account.id}`)
  if (editingAccountId.value === account.id) {
    resetAccountForm()
  }
  await loadAccounts()
}

async function openBacktest(backtest: BacktestListItem) {
  if (isSelectedBacktest(backtest) && !backtestDetailLoading.value) {
    closeBacktestDetail()
    return
  }

  await openBacktestById(backtest.id)
}

async function openBacktestById(backtestId: number) {
  backtestDetailLoading.value = true
  backtestError.value = ''
  try {
    const response = await apiClient.get<BacktestDetail>(`/backtests/${backtestId}`)
    selectedBacktest.value = response.data
  } catch {
    backtestError.value = '回测详情加载失败'
  } finally {
    backtestDetailLoading.value = false
  }
}

function isSelectedBacktest(backtest: BacktestListItem) {
  return selectedBacktest.value?.id === backtest.id
}

async function openBacktestFromRouteQuery() {
  const rawBacktestId = Array.isArray(route.query.backtestId)
    ? route.query.backtestId[0]
    : route.query.backtestId
  const backtestId = Number(rawBacktestId)
  if (!Number.isInteger(backtestId) || backtestId <= 0) {
    return
  }

  activeTab.value = 'backtests'
  await openBacktestById(backtestId)
}

function closeBacktestDetail() {
  selectedBacktest.value = null
  backtestError.value = ''
}

function replaySelectedBacktestStrategy() {
  const backtest = selectedBacktest.value
  if (!backtest) {
    return
  }

  workspaceStore.openBacktestSnapshot({
    name: `回测复盘：${backtest.symbol} ${formatTimeframe(backtest.timeframe)}`,
    description: `来自回测记录 ${backtest.runId}`,
    strategy: backtest.strategy,
    backtestConfig: {
      market: backtest.config.market,
      symbol: backtest.config.symbol,
      timeframe: backtest.config.timeframe,
      startDate: backtest.config.startDate,
      endDate: backtest.config.endDate,
      initialCash: backtest.config.initialCash,
      ...(backtest.simulationAccountId
        ? { simulationAccountId: backtest.simulationAccountId }
        : {})
    },
    statusMessage: `已载入回测策略快照：${backtest.symbol}`
  })
  void router.push('/')
}

async function changeStrategyPage(nextPage: number) {
  if (nextPage < 1 || nextPage > strategyTotalPages.value || nextPage === strategyPage.value) {
    return
  }
  strategyPage.value = nextPage
  await loadStrategies()
}

async function changeCustomBlockPage(nextPage: number) {
  if (
    nextPage < 1 ||
    nextPage > customBlockTotalPages.value ||
    nextPage === customBlockPage.value
  ) {
    return
  }
  customBlockPage.value = nextPage
  await loadCustomBlocks()
}

async function changeAccountPage(nextPage: number) {
  if (nextPage < 1 || nextPage > accountTotalPages.value || nextPage === accountPage.value) {
    return
  }
  accountPage.value = nextPage
  await loadAccounts()
}

async function changeBacktestPage(nextPage: number) {
  if (nextPage < 1 || nextPage > backtestTotalPages.value || nextPage === backtestPage.value) {
    return
  }
  backtestPage.value = nextPage
  selectedBacktest.value = null
  await loadBacktests()
}

async function changeFilePage(nextPage: number) {
  if (nextPage < 1 || nextPage > fileTotalPages.value || nextPage === filePage.value) {
    return
  }
  filePage.value = nextPage
  await loadFiles()
}

async function changeForumPostPage(nextPage: number) {
  if (
    nextPage < 1 ||
    nextPage > forumPostTotalPages.value ||
    nextPage === forumPostPage.value
  ) {
    return
  }
  forumPostPage.value = nextPage
  await loadForumPosts()
}

async function changeForumCommentPage(nextPage: number) {
  if (
    nextPage < 1 ||
    nextPage > forumCommentTotalPages.value ||
    nextPage === forumCommentPage.value
  ) {
    return
  }
  forumCommentPage.value = nextPage
  await loadForumComments()
}

function formatMarket(market: BacktestListItem['market'] | undefined) {
  if (market === 'US_STOCK') {
    return '美股'
  }
  return 'A股'
}

function formatMarketRuleSessions(rule: MarketRule) {
  return rule.sessions.map((session) => `${session.start}-${session.end}`).join(' / ')
}

function formatMarketRuleRoundTrip(rule: MarketRule) {
  return rule.supportsIntradayRoundTrip ? '日内买卖' : 'T+1，当日买入不可卖'
}

function formatMarketRulePriceLimit(rule: MarketRule) {
  if (rule.priceLimitPercent === null) {
    return '无固定涨跌停'
  }
  return `涨跌停 ${formatPercent(rule.priceLimitPercent)}`
}

function formatTimeframe(timeframe: string | undefined) {
  return timeframe === '1m' ? '1分钟' : '5分钟'
}

function formatPercent(value: number | undefined) {
  return `${Number(value ?? 0)
    .toFixed(2)
    .replace(/\.00$/, '')
    .replace(/(\.\d)0$/, '$1')}%`
}

function formatAmount(value: number | undefined) {
  return Number(value ?? 0).toLocaleString('zh-CN', {
    maximumFractionDigits: 2
  })
}

function formatDate(value: string | undefined) {
  return value ? value.slice(0, 10) : '-'
}

function formatFileSize(size: number) {
  if (size < 1024) {
    return `${size} B`
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1).replace(/\.0$/, '')} KB`
  }
  return `${(size / 1024 / 1024).toFixed(1).replace(/\.0$/, '')} MB`
}

function formatBusinessType(type: string) {
  const labels: Record<string, string> = {
    backtest: '回测附件',
    custom_block: '积木附件',
    forum: '论坛附件',
    general: '普通文件',
    strategy: '策略附件'
  }
  return labels[type] ?? '普通文件'
}

function formatReviewStatus(status: CustomBlock['reviewStatus']) {
  const labels: Record<CustomBlock['reviewStatus'], string> = {
    private: '私有模板',
    pending_review: '待审核',
    approved: '已公开',
    rejected: '未通过'
  }
  return labels[status] ?? '私有模板'
}

function formatForumReviewStatus(status: ForumReviewStatus) {
  const labels: Record<ForumReviewStatus, string> = {
    pending_review: '审核中',
    approved: '已通过',
    rejected: '未通过审核'
  }
  return labels[status] ?? '审核中'
}

function normalizedCustomBlockName(name: string) {
  return name.trim().toLowerCase()
}

function customBlockDisplayName(block: CustomBlock) {
  const duplicateCount = customBlockNameCounts.value.get(normalizedCustomBlockName(block.name)) ?? 0
  return duplicateCount > 1 ? `${block.name} #${block.id}` : block.name
}

function formatConnectionCount(count: number) {
  return `${count} 条连接`
}

watch(
  () => authStore.isAuthenticated,
  (isAuthenticated, wasAuthenticated) => {
    if (isAuthenticated && !wasAuthenticated) {
      void loadSpaceData()
    }
  }
)

watch(
  () => route.query.tab,
  (tab) => {
    activeTab.value = spaceTabFromQuery(tab)
  }
)

onMounted(() => {
  void (async () => {
    await loadSpaceData()
    await openBacktestFromRouteQuery()
  })()
})
</script>

<template>
  <section class="page-panel personal-space">
    <header class="space-header">
      <div>
        <h1>个人空间</h1>
        <p>策略资产、回测记录与个人沉淀</p>
      </div>
      <form
        v-if="activeTab !== 'overview' && activeTab !== 'forum'"
        class="space-search"
        @submit.prevent="searchActiveTab"
      >
        <input
          v-if="activeTab === 'strategies'"
          v-model="strategyKeyword"
          placeholder="搜索策略"
        />
        <input
          v-else-if="activeTab === 'custom-blocks'"
          v-model="customBlockKeyword"
          placeholder="搜索积木名称、分类"
        />
        <input
          v-else-if="activeTab === 'accounts'"
          v-model="accountKeyword"
          placeholder="搜索账户、市场"
        />
        <input
          v-else-if="activeTab === 'files'"
          v-model="fileKeyword"
          placeholder="搜索文件名、类型"
        />
        <input
          v-else
          v-model="backtestKeyword"
          placeholder="搜索股票、市场、周期"
        />
        <button type="submit">搜索</button>
      </form>
    </header>

    <nav class="space-tabs" aria-label="个人空间页面">
      <button
        type="button"
        data-space-tab="overview"
        :class="{ 'is-active': activeTab === 'overview' }"
        @click="activeTab = 'overview'"
      >
        概览
      </button>
      <button
        type="button"
        data-space-tab="strategies"
        :class="{ 'is-active': activeTab === 'strategies' }"
        @click="activeTab = 'strategies'"
      >
        我的策略
      </button>
      <button
        type="button"
        data-space-tab="custom-blocks"
        :class="{ 'is-active': activeTab === 'custom-blocks' }"
        @click="activeTab = 'custom-blocks'"
      >
        我的积木
      </button>
      <button
        type="button"
        data-space-tab="accounts"
        :class="{ 'is-active': activeTab === 'accounts' }"
        @click="activeTab = 'accounts'"
      >
        模拟账户
      </button>
      <button
        type="button"
        data-space-tab="backtests"
        :class="{ 'is-active': activeTab === 'backtests' }"
        @click="activeTab = 'backtests'"
      >
        我的回测
      </button>
      <button
        type="button"
        data-space-tab="files"
        :class="{ 'is-active': activeTab === 'files' }"
        @click="activeTab = 'files'"
      >
        文件管理
      </button>
      <button
        type="button"
        data-space-tab="forum"
        :class="{ 'is-active': activeTab === 'forum' }"
        @click="activeTab = 'forum'"
      >
        我的论坛
      </button>
    </nav>

    <section v-if="activeTab === 'overview'" class="space-overview">
      <div class="space-overview-grid">
        <article class="space-metric">
          <small>策略总数</small>
          <strong>{{ strategyTotal }}</strong>
        </article>
        <article class="space-metric">
          <small>积木总数</small>
          <strong>{{ customBlockTotal }}</strong>
        </article>
        <article class="space-metric">
          <small>回测总数</small>
          <strong>{{ backtestTotal }}</strong>
        </article>
        <article class="space-metric">
          <small>账户总数</small>
          <strong>{{ accountTotal }}</strong>
        </article>
        <article class="space-metric">
          <small>论坛内容</small>
          <strong>{{ forumContentTotal }}</strong>
        </article>
        <article class="space-metric">
          <small>文件总数</small>
          <strong>{{ fileTotal }}</strong>
        </article>
        <article class="space-metric">
          <small>最佳收益</small>
          <strong>{{ formatPercent(bestBacktest?.totalReturnPercent) }}</strong>
        </article>
        <article class="space-metric">
          <small>最低回撤</small>
          <strong>{{ formatPercent(lowestDrawdownBacktest?.maxDrawdownPercent) }}</strong>
        </article>
      </div>

      <div class="space-overview-lanes">
        <article class="space-lane">
          <div>
            <small>最近策略</small>
            <h2>{{ latestStrategy?.name || '暂无策略' }}</h2>
            <p v-if="latestStrategy">
              {{ latestStrategy.backtestConfig?.symbol || '未设置股票' }}
              ·
              {{ formatTimeframe(latestStrategy.backtestConfig?.timeframe) }}
            </p>
          </div>
          <button
            v-if="latestStrategy"
            class="strategy-open-button"
            type="button"
            @click="openStrategy(latestStrategy)"
          >
            打开
          </button>
        </article>
        <article class="space-lane">
          <div>
            <small>最近积木</small>
            <h2>{{ latestCustomBlock ? customBlockDisplayName(latestCustomBlock) : '暂无积木' }}</h2>
            <p v-if="latestCustomBlock">
              {{ latestCustomBlock.category }}
              ·
              {{ latestCustomBlock.template.nodes.length }} 个积木
              ·
              {{ formatReviewStatus(latestCustomBlock.reviewStatus) }}
            </p>
          </div>
          <button
            v-if="latestCustomBlock"
            type="button"
            @click="activeTab = 'custom-blocks'"
          >
            管理
          </button>
        </article>
        <article class="space-lane">
          <div>
            <small>最近账户</small>
            <h2>{{ latestAccount?.name || '暂无账户' }}</h2>
            <p v-if="latestAccount">
              {{ formatMarket(latestAccount.market) }}
              ·
              初始资金 {{ latestAccount.initialCash }}
            </p>
          </div>
          <button
            v-if="latestAccount"
            type="button"
            @click="activeTab = 'accounts'"
          >
            管理
          </button>
        </article>
        <article class="space-lane">
          <div>
            <small>最近回测</small>
            <h2>{{ latestBacktest?.symbol || '暂无回测' }}</h2>
            <p v-if="latestBacktest">
              {{ formatMarket(latestBacktest.market) }}
              ·
              {{ formatTimeframe(latestBacktest.timeframe) }}
              ·
              {{ formatPercent(latestBacktest.totalReturnPercent) }}
            </p>
          </div>
          <button
            v-if="latestBacktest"
            class="backtest-open-button"
            type="button"
            @click="openBacktest(latestBacktest)"
          >
            查看
          </button>
        </article>
        <article class="space-lane">
          <div>
            <small>最近论坛</small>
            <h2>{{ latestForumPost?.title || '暂无论坛内容' }}</h2>
            <p v-if="latestForumPost">
              {{ latestForumPost.topic }}
              ·
              {{ formatForumReviewStatus(latestForumPost.reviewStatus) }}
            </p>
          </div>
          <button
            v-if="latestForumPost"
            type="button"
            @click="activeTab = 'forum'"
          >
            查看
          </button>
        </article>
        <article class="space-lane">
          <div>
            <small>最近文件</small>
            <h2>{{ latestFile?.originalName || '暂无文件' }}</h2>
            <p v-if="latestFile">
              {{ formatBusinessType(latestFile.businessType) }}
              ·
              {{ formatFileSize(latestFile.size) }}
              ·
              {{ formatDate(latestFile.createdAt) }}
            </p>
          </div>
          <button
            v-if="latestFile"
            type="button"
            @click="activeTab = 'files'"
          >
            管理
          </button>
        </article>
      </div>

      <aside v-if="selectedBacktest" class="space-detail-panel">
        <strong>回测详情</strong>
        <span>{{ selectedBacktest.symbol }} · {{ formatPercent(selectedBacktest.summary.totalReturnPercent) }}</span>
      </aside>
    </section>

    <section v-else-if="activeTab === 'strategies'" class="space-section">
      <p v-if="strategyError" class="form-error">{{ strategyError }}</p>
      <p v-if="strategyActionError" class="form-error">{{ strategyActionError }}</p>
      <p v-if="strategyActionMessage" class="space-muted">{{ strategyActionMessage }}</p>
      <p v-if="strategyLoading" class="space-muted">正在加载策略</p>
      <p
        v-else-if="!strategyError && strategies.length === 0"
        class="space-muted"
      >
        暂无已保存策略
      </p>

      <div
        v-if="!strategyError && !strategyLoading && strategies.length > 0"
        class="strategy-list"
      >
        <article v-for="strategy in strategies" :key="strategy.id" class="strategy-item">
          <div class="strategy-item-main">
            <h2>{{ strategy.name }}</h2>
            <p>{{ strategy.description || '无描述' }}</p>
            <small>
              {{ strategy.backtestConfig?.symbol || '未设置股票' }}
              ·
              {{ formatTimeframe(strategy.backtestConfig?.timeframe) }}
              ·
              更新于 {{ formatDate(strategy.updatedAt) }}
            </small>
            <form
              v-if="editingStrategyId === strategy.id"
              class="strategy-rename-form"
              @submit.prevent="submitStrategyRename(strategy)"
            >
              <label>
                <span>策略名称</span>
                <input
                  v-model="strategyNameForm"
                  class="strategy-name-input"
                  maxlength="80"
                />
              </label>
              <div class="strategy-rename-actions">
                <button
                  class="strategy-save-name-button"
                  type="submit"
                  :disabled="isSavingStrategyName"
                  @click.prevent="submitStrategyRename(strategy)"
                >
                  {{ isSavingStrategyName ? '保存中' : '保存修改' }}
                </button>
                <button
                  class="strategy-cancel-rename-button"
                  type="button"
                  @click="cancelStrategyRename"
                >
                  取消
                </button>
              </div>
            </form>
          </div>
          <div class="strategy-item-actions">
            <button class="strategy-open-button" type="button" @click="openStrategy(strategy)">
              打开
            </button>
            <button
              class="strategy-rename-button"
              type="button"
              @click="editStrategyName(strategy)"
            >
              重命名
            </button>
            <button class="strategy-delete-button" type="button" @click="deleteStrategy(strategy)">
              删除
            </button>
          </div>
        </article>
      </div>

      <footer class="space-footer">
        <span>共 {{ strategyTotal }} 条策略</span>
        <div class="space-pagination">
          <button
            type="button"
            data-pagination="strategies-prev"
            :disabled="strategyPage <= 1"
            @click="changeStrategyPage(strategyPage - 1)"
          >
            上一页
          </button>
          <span>第 {{ strategyPage }} / {{ strategyTotalPages }} 页</span>
          <button
            type="button"
            data-pagination="strategies-next"
            :disabled="strategyPage >= strategyTotalPages"
            @click="changeStrategyPage(strategyPage + 1)"
          >
            下一页
          </button>
        </div>
      </footer>
    </section>

    <section v-else-if="activeTab === 'custom-blocks'" class="space-section">
      <p v-if="customBlockError" class="form-error">{{ customBlockError }}</p>
      <p v-else-if="customBlockLoading" class="space-muted">正在加载自定义积木</p>
      <p v-else-if="customBlocks.length === 0" class="space-muted">暂无自定义积木</p>
      <p v-if="customBlockActionError" class="form-error">{{ customBlockActionError }}</p>
      <p v-if="customBlockActionMessage" class="space-muted">{{ customBlockActionMessage }}</p>

      <div
        v-if="!customBlockError && !customBlockLoading && customBlocks.length > 0"
        class="custom-block-list"
      >
        <article v-for="block in customBlocks" :key="block.id" class="custom-block-item">
          <div class="custom-block-main">
            <div>
              <h2>{{ customBlockDisplayName(block) }}</h2>
              <p>{{ block.description || '无描述' }}</p>
              <small>
                {{ block.category }}
                ·
                {{ formatReviewStatus(block.reviewStatus) }}
                ·
                {{ block.template.nodes.length }} 个积木
                ·
                {{ formatConnectionCount(block.template.edges.length) }}
                ·
                更新于 {{ formatDate(block.updatedAt) }}
              </small>
              <div v-if="block.tags.length" class="custom-block-tags">
                <span v-for="tag in block.tags" :key="tag">{{ tag }}</span>
              </div>
              <div class="custom-block-node-summary" aria-label="积木节点摘要">
                <span
                  v-for="summary in summarizeStrategyBlocks(block.template)"
                  :key="summary.label"
                >
                  {{ summary.label }} x{{ summary.count }}
                </span>
              </div>
            </div>

            <form
              v-if="editingCustomBlockId === block.id"
              class="custom-block-edit-form"
              @submit.prevent="submitCustomBlock(block)"
            >
              <label>
                <span>积木名称</span>
                <input v-model="customBlockForm.name" class="custom-block-name-input" />
              </label>
              <label>
                <span>分类</span>
                <input v-model="customBlockForm.category" class="custom-block-category-input" />
              </label>
              <label>
                <span>描述</span>
                <textarea
                  v-model="customBlockForm.description"
                  class="custom-block-description-input"
                ></textarea>
              </label>
              <label>
                <span>标签</span>
                <input
                  v-model="customBlockForm.tags"
                  class="custom-block-tags-input"
                  placeholder="用逗号分隔"
                />
              </label>
              <div class="custom-block-edit-actions">
                <button
                  class="custom-block-save-button"
                  type="submit"
                  @click.prevent="submitCustomBlock(block)"
                >
                  保存修改
                </button>
                <button
                  class="custom-block-cancel-button"
                  type="button"
                  @click="cancelCustomBlockEdit"
                >
                  取消
                </button>
              </div>
            </form>

            <div
              v-if="confirmingCustomBlockDeleteId === block.id"
              class="custom-block-delete-confirm"
            >
              <span>确认删除这个积木吗？</span>
              <button
                class="custom-block-confirm-delete-button"
                type="button"
                @click="confirmDeleteCustomBlock(block)"
              >
                确认删除
              </button>
              <button
                class="custom-block-cancel-button"
                type="button"
                @click="cancelDeleteCustomBlock"
              >
                取消
              </button>
            </div>
          </div>
          <div class="strategy-item-actions">
            <button
              class="custom-block-publish-button"
              type="button"
              :disabled="!canPublishCustomBlock(block)"
              @click="publishCustomBlock(block)"
            >
              {{ customBlockPublishLabel(block) }}
            </button>
            <button class="custom-block-use-button" type="button" @click="openCustomBlock(block)">
              使用
            </button>
            <button class="custom-block-edit-button" type="button" @click="editCustomBlock(block)">
              编辑
            </button>
            <button
              class="custom-block-delete-button"
              type="button"
              @click="requestDeleteCustomBlock(block)"
            >
              删除
            </button>
          </div>
        </article>
      </div>

      <footer class="space-footer">
        <span>共 {{ customBlockTotal }} 个积木</span>
        <div class="space-pagination">
          <button
            type="button"
            data-pagination="custom-blocks-prev"
            :disabled="customBlockPage <= 1"
            @click="changeCustomBlockPage(customBlockPage - 1)"
          >
            上一页
          </button>
          <span>第 {{ customBlockPage }} / {{ customBlockTotalPages }} 页</span>
          <button
            type="button"
            data-pagination="custom-blocks-next"
            :disabled="customBlockPage >= customBlockTotalPages"
            @click="changeCustomBlockPage(customBlockPage + 1)"
          >
            下一页
          </button>
        </div>
      </footer>
    </section>

    <section v-else-if="activeTab === 'accounts'" class="space-section">
      <p v-if="accountError" class="form-error">{{ accountError }}</p>

      <div class="account-layout">
        <form class="account-form" @submit.prevent="submitAccount">
          <strong>{{ editingAccountId ? '编辑模拟账户' : '创建模拟账户' }}</strong>
          <label>
            <span>账户名称</span>
            <input
              v-model="accountForm.name"
              class="account-name-input"
              required
              maxlength="80"
              placeholder="例如 A股日内账户"
            />
          </label>
          <label>
            <span>市场</span>
            <select v-model="accountForm.market" class="account-market-select">
              <option value="A_SHARE">A股</option>
              <option value="US_STOCK">美股</option>
            </select>
          </label>
          <section v-if="selectedMarketRule" class="market-rule-card">
            <header>
              <strong>当前按 {{ selectedMarketRule.marketLabel }} 规则模拟</strong>
              <small>{{ selectedMarketRule.currency }} · {{ selectedMarketRule.timezone }}</small>
            </header>
            <dl>
              <div>
                <dt>交易时段</dt>
                <dd>{{ formatMarketRuleSessions(selectedMarketRule) }}</dd>
              </div>
              <div>
                <dt>结算</dt>
                <dd>{{ selectedMarketRule.settlementCycle }}</dd>
              </div>
              <div>
                <dt>买入单位</dt>
                <dd>每笔买入 {{ selectedMarketRule.buyLotSize }} 股</dd>
              </div>
              <div>
                <dt>日内规则</dt>
                <dd>{{ formatMarketRuleRoundTrip(selectedMarketRule) }}</dd>
              </div>
              <div>
                <dt>价格限制</dt>
                <dd>{{ formatMarketRulePriceLimit(selectedMarketRule) }}</dd>
              </div>
            </dl>
            <ul>
              <li v-for="note in selectedMarketRule.notes" :key="note">{{ note }}</li>
            </ul>
          </section>
          <p v-else-if="marketRuleError" class="space-muted">{{ marketRuleError }}</p>
          <label>
            <span>初始资金</span>
            <input
              v-model.number="accountForm.initialCash"
              class="account-cash-input"
              type="number"
              min="1"
              required
            />
          </label>
          <label>
            <span>备注</span>
            <textarea
              v-model="accountForm.description"
              class="account-description-input"
              maxlength="500"
              placeholder="用途、周期或资金规则"
            />
          </label>
          <div class="account-form-actions">
            <button class="account-submit-button" type="submit" @click.prevent="submitAccount">
              {{ editingAccountId ? '保存修改' : '创建账户' }}
            </button>
            <button v-if="editingAccountId" type="button" @click="resetAccountForm">
              取消
            </button>
          </div>
        </form>

        <div class="account-list">
          <p v-if="accountLoading" class="space-muted">正在加载模拟账户</p>
          <p v-else-if="accounts.length === 0" class="space-muted">暂无模拟账户</p>
          <article v-for="account in accounts" v-else :key="account.id" class="account-item">
            <div>
              <h2>{{ account.name }}</h2>
              <p>{{ account.description || '无描述' }}</p>
              <small>
                {{ formatMarket(account.market) }}
                ·
                初始资金 {{ account.initialCash }}
                ·
                更新于 {{ formatDate(account.updatedAt) }}
              </small>
            </div>
            <div class="strategy-item-actions">
              <button class="account-edit-button" type="button" @click="editAccount(account)">
                编辑
              </button>
              <button class="account-delete-button" type="button" @click="deleteAccount(account)">
                删除
              </button>
            </div>
          </article>
        </div>
      </div>

      <footer class="space-footer">
        <span>共 {{ accountTotal }} 个账户</span>
        <div class="space-pagination">
          <button
            type="button"
            data-pagination="accounts-prev"
            :disabled="accountPage <= 1"
            @click="changeAccountPage(accountPage - 1)"
          >
            上一页
          </button>
          <span>第 {{ accountPage }} / {{ accountTotalPages }} 页</span>
          <button
            type="button"
            data-pagination="accounts-next"
            :disabled="accountPage >= accountTotalPages"
            @click="changeAccountPage(accountPage + 1)"
          >
            下一页
          </button>
        </div>
      </footer>
    </section>

    <section v-else-if="activeTab === 'files'" class="space-section">
      <p v-if="fileError" class="form-error">{{ fileError }}</p>
      <p v-if="fileActionError" class="form-error">{{ fileActionError }}</p>
      <p v-if="fileActionMessage" class="space-muted">{{ fileActionMessage }}</p>

      <form class="file-upload-form" @submit.prevent="uploadSelectedFile">
        <div>
          <strong>上传文件</strong>
          <p>保存策略说明、回测记录、截图或表格等个人附件。</p>
        </div>
        <label>
          <span>选择文件</span>
          <input
            ref="fileInputRef"
            class="file-upload-input"
            type="file"
            @change="handleFileSelection"
          />
        </label>
        <button
          class="file-upload-button"
          type="submit"
          :disabled="isUploadingFile"
          @click.prevent="uploadSelectedFile"
        >
          {{ isUploadingFile ? '上传中' : '上传文件' }}
        </button>
      </form>

      <p v-if="fileLoading" class="space-muted">正在加载文件</p>
      <p v-else-if="!fileError && uploadedFiles.length === 0" class="space-muted">暂无文件</p>

      <div
        v-if="!fileError && !fileLoading && uploadedFiles.length > 0"
        class="file-list"
      >
        <article v-for="file in uploadedFiles" :key="file.id" class="file-item">
          <div>
            <h2>{{ file.originalName }}</h2>
            <p>
              {{ formatBusinessType(file.businessType) }}
              ·
              {{ file.contentType }}
            </p>
            <small>
              {{ formatFileSize(file.size) }}
              ·
              上传于 {{ formatDate(file.createdAt) }}
            </small>
          </div>
          <div class="strategy-item-actions">
            <button class="file-download-button" type="button" @click="downloadFile(file)">
              下载
            </button>
            <button class="file-delete-button" type="button" @click="deleteFile(file)">
              删除
            </button>
          </div>
        </article>
      </div>

      <footer class="space-footer">
        <span>共 {{ fileTotal }} 个文件</span>
        <div class="space-pagination">
          <button
            type="button"
            data-pagination="files-prev"
            :disabled="filePage <= 1"
            @click="changeFilePage(filePage - 1)"
          >
            上一页
          </button>
          <span>第 {{ filePage }} / {{ fileTotalPages }} 页</span>
          <button
            type="button"
            data-pagination="files-next"
            :disabled="filePage >= fileTotalPages"
            @click="changeFilePage(filePage + 1)"
          >
            下一页
          </button>
        </div>
      </footer>
    </section>

    <section v-else-if="activeTab === 'forum'" class="space-section space-forum">
      <div class="space-forum-tabs" role="tablist" aria-label="我的论坛内容">
        <button
          class="space-forum-posts-tab"
          :class="{ 'is-active': activeForumTab === 'posts' }"
          type="button"
          @click="activeForumTab = 'posts'"
        >
          我的帖子
          <span>{{ forumPostTotal }}</span>
        </button>
        <button
          class="space-forum-comments-tab"
          :class="{ 'is-active': activeForumTab === 'comments' }"
          type="button"
          @click="activeForumTab = 'comments'"
        >
          我的评论
          <span>{{ forumCommentTotal }}</span>
        </button>
      </div>

      <div v-if="activeForumTab === 'posts'" class="space-forum-list">
        <p v-if="forumPostError" class="form-error">{{ forumPostError }}</p>
        <p v-else-if="forumPostLoading" class="space-muted">正在加载我的帖子</p>
        <p v-else-if="forumPosts.length === 0" class="space-muted">暂无论坛帖子</p>
        <article v-for="post in forumPosts" v-else :key="post.id" class="strategy-item forum-space-item">
          <div>
            <div class="forum-space-meta">
              <span>{{ post.topic }}</span>
              <span>{{ formatDate(post.updatedAt) }}</span>
              <span class="forum-space-status">{{ formatForumReviewStatus(post.reviewStatus) }}</span>
            </div>
            <h2>{{ post.title }}</h2>
            <p>{{ post.content }}</p>
            <small
              v-if="post.reviewStatus === 'rejected' && post.reviewReason"
              class="forum-review-reason"
            >
              未通过原因：{{ post.reviewReason }}
            </small>
            <small>评论 {{ post.commentCount }}</small>
          </div>
          <div class="strategy-item-actions">
            <a v-if="post.reviewStatus === 'approved'" :href="`/forum?postId=${post.id}`">
              查看公开帖
            </a>
          </div>
        </article>

        <footer class="space-footer">
          <span>共 {{ forumPostTotal }} 条帖子</span>
          <div class="space-pagination">
            <button
              type="button"
              data-pagination="forum-posts-prev"
              :disabled="forumPostPage <= 1"
              @click="changeForumPostPage(forumPostPage - 1)"
            >
              上一页
            </button>
            <span>第 {{ forumPostPage }} / {{ forumPostTotalPages }} 页</span>
            <button
              type="button"
              data-pagination="forum-posts-next"
              :disabled="forumPostPage >= forumPostTotalPages"
              @click="changeForumPostPage(forumPostPage + 1)"
            >
              下一页
            </button>
          </div>
        </footer>
      </div>

      <div v-else class="space-forum-list">
        <p v-if="forumCommentError" class="form-error">{{ forumCommentError }}</p>
        <p v-else-if="forumCommentLoading" class="space-muted">正在加载我的评论</p>
        <p v-else-if="forumComments.length === 0" class="space-muted">暂无论坛评论</p>
        <article
          v-for="comment in forumComments"
          v-else
          :key="comment.id"
          class="strategy-item forum-space-item"
        >
          <div>
            <div class="forum-space-meta">
              <span>关联帖子：{{ comment.postTitle }}</span>
              <span>{{ formatDate(comment.updatedAt) }}</span>
              <span class="forum-space-status">
                {{ formatForumReviewStatus(comment.reviewStatus) }}
              </span>
            </div>
            <h2>{{ comment.postTitle }}</h2>
            <p>{{ comment.content }}</p>
            <small
              v-if="comment.reviewStatus === 'rejected' && comment.reviewReason"
              class="forum-review-reason"
            >
              未通过原因：{{ comment.reviewReason }}
            </small>
          </div>
        </article>

        <footer class="space-footer">
          <span>共 {{ forumCommentTotal }} 条评论</span>
          <div class="space-pagination">
            <button
              type="button"
              data-pagination="forum-comments-prev"
              :disabled="forumCommentPage <= 1"
              @click="changeForumCommentPage(forumCommentPage - 1)"
            >
              上一页
            </button>
            <span>第 {{ forumCommentPage }} / {{ forumCommentTotalPages }} 页</span>
            <button
              type="button"
              data-pagination="forum-comments-next"
              :disabled="forumCommentPage >= forumCommentTotalPages"
              @click="changeForumCommentPage(forumCommentPage + 1)"
            >
              下一页
            </button>
          </div>
        </footer>
      </div>
    </section>

    <section v-else class="space-section space-backtests">
      <p v-if="backtestError" class="form-error">{{ backtestError }}</p>
      <p v-else-if="backtestLoading" class="space-muted">正在加载回测</p>
      <p v-else-if="backtests.length === 0" class="space-muted">暂无回测记录</p>

      <div v-else class="backtest-layout">
        <div class="backtest-list">
          <article
            v-for="backtest in backtests"
            :key="backtest.id"
            class="backtest-item"
            :class="{ 'is-selected': isSelectedBacktest(backtest) }"
          >
            <div>
              <h2>{{ backtest.symbol }}</h2>
              <p>
                {{ formatMarket(backtest.market) }}
                ·
                {{ formatTimeframe(backtest.timeframe) }}
                ·
                {{ backtest.startDate }} 至 {{ backtest.endDate }}
              </p>
              <small>
                收益 {{ formatPercent(backtest.totalReturnPercent) }}
                ·
                最大回撤 {{ formatPercent(backtest.maxDrawdownPercent) }}
                ·
                {{ backtest.tradeCount }} 笔
                <template v-if="backtest.simulationAccountName">
                  ·
                  使用账户 {{ backtest.simulationAccountName }}
                </template>
              </small>
            </div>
            <button class="backtest-open-button" type="button" @click="openBacktest(backtest)">
              {{ isSelectedBacktest(backtest) ? '收起' : '查看' }}
            </button>
          </article>
        </div>

        <aside class="space-detail-panel" :aria-busy="backtestDetailLoading">
          <template v-if="selectedBacktest">
            <header class="detail-panel-header">
              <strong>回测详情</strong>
              <button class="backtest-close-button" type="button" @click="closeBacktestDetail">
                收起
              </button>
            </header>
            <div class="backtest-detail-metrics">
              <span>
                <small>收益</small>
                <b>{{ formatPercent(selectedBacktest.summary.totalReturnPercent) }}</b>
              </span>
              <span>
                <small>回撤</small>
                <b>{{ formatPercent(selectedBacktest.summary.maxDrawdownPercent) }}</b>
              </span>
              <span>
                <small>资产</small>
                <b>{{ selectedBacktest.summary.endingEquity }}</b>
              </span>
            </div>
            <p v-if="selectedBacktest.simulationAccountName" class="space-muted">
              账户 {{ selectedBacktest.simulationAccountName }}
            </p>
            <section class="backtest-snapshot">
              <header>
                <strong>回测快照</strong>
                <div class="snapshot-header-actions">
                  <small>策略积木 {{ selectedBacktest.strategy.nodes.length }} 个</small>
                  <button
                    class="backtest-replay-button"
                    type="button"
                    @click="replaySelectedBacktestStrategy"
                  >
                    复盘策略
                  </button>
                </div>
              </header>
              <dl class="snapshot-grid">
                <div v-for="field in selectedBacktestSnapshotFields" :key="field.label">
                  <dt>{{ field.label }}</dt>
                  <dd>{{ field.value }}</dd>
                </div>
              </dl>
              <div class="strategy-block-summary" aria-label="策略积木摘要">
                <span>策略积木</span>
                <ul>
                  <li
                    v-for="summary in selectedStrategyBlockSummaries"
                    :key="summary.label"
                  >
                    {{ summary.label }} x{{ summary.count }}
                  </li>
                </ul>
              </div>
            </section>
            <BacktestResultVisualization :result="selectedBacktest" />
            <p class="space-muted">
              最新资金 {{ selectedBacktest.equityCurve[selectedBacktest.equityCurve.length - 1]?.equity }}
            </p>
          </template>
          <p v-else class="space-muted">选择一条回测记录</p>
        </aside>
      </div>

      <footer class="space-footer">
        <span>共 {{ backtestTotal }} 条回测</span>
        <div class="space-pagination">
          <button
            type="button"
            data-pagination="backtests-prev"
            :disabled="backtestPage <= 1"
            @click="changeBacktestPage(backtestPage - 1)"
          >
            上一页
          </button>
          <span>第 {{ backtestPage }} / {{ backtestTotalPages }} 页</span>
          <button
            type="button"
            data-pagination="backtests-next"
            :disabled="backtestPage >= backtestTotalPages"
            @click="changeBacktestPage(backtestPage + 1)"
          >
            下一页
          </button>
        </div>
      </footer>
    </section>
  </section>
</template>
