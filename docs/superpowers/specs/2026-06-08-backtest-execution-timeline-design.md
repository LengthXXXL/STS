# 回测执行时间线 V1 设计

## 目标

把当前回测结果从“指标 + 成交表 + 规则提示”升级为更容易理解的执行复盘：

用户运行回测后，可以按时间顺序看到策略在每个关键时刻做了什么、为什么做、是否成交、如果未成交是被哪条市场规则拦截。

本阶段不追求专业报告的完整复杂度，而是先满足 PRD 的可解释性要求：

- 每次交易触发的积木
- 成交价格
- 未成交原因
- 市场规则限制原因

外部回测产品和文档通常都会把 trade log、equity curve、logs 或 execution context 作为结果分析的重要部分，例如 QuantConnect 的结果页包含 equity curve、trades、logs 和统计信息，ML4T 的 BacktestResult 也包含 trades、fills、equity curve 和 portfolio state。这说明 STS 的下一步不应该只堆指标，而应该让用户看懂策略执行过程。

参考：

- https://www.quantconnect.com/docs/v2/cloud-platform/backtesting/results
- https://ml4trading.io/docs/backtest/user-guide/results/
- https://quanthop.com/learn/backtesting-fundamentals/how-backtesting-works

## 范围

本阶段包含：

- 后端回测响应新增 `timeline` 字段。
- 保存回测时，把 `timeline` 一起保存到数据库。
- 个人空间打开回测详情时返回 `timeline`。
- 搭建页回测结果展示“策略执行时间线”。
- 个人空间回测详情展示“策略执行时间线”。
- 时间线覆盖成交、未成交、冷却开始、持仓关闭这些关键事件。
- 继续保留现有 `trades`、`events`、`equityCurve` 字段，避免破坏已有界面和测试。

本阶段不包含：

- 手续费真实扣减。
- 滑点真实扣减。
- 逐 K 线完整状态日志。
- 逐笔持仓成本变化表。
- 可筛选、可导出的专业回测报告。
- 使用 ECharts 重做走势图。

## 用户体验

### 搭建页

用户点击“运行回测”后，在回测结果卡片中看到：

1. 核心指标：总收益率、最大回撤、胜率、期末资产。
2. 策略执行时间线：主视图，按时间排序。
3. 成交明细：保留为明细表。
4. 规则提示：保留为兼容视图，后续可以逐步被时间线吸收。

时间线标题为“策略执行时间线”。

每条时间线记录显示：

- 时间
- 事件名称
- 简短说明
- 价格、数量、方向等交易字段
- 触发积木
- 市场规则或冷却规则

### 个人空间

用户进入“我的回测”，点击某条回测后，在详情面板中看到同样的“策略执行时间线”。

如果该回测是旧数据，没有 `timeline`，前端不报错；V1 直接隐藏时间线区域，不从 `trades`、`events` 反推历史时间线，避免旧数据出现看似完整但实际缺少触发上下文的解释。

## 时间线事件类型

### `TRADE_FILLED`

表示一次真实成交。

适用场景：

- 买入积木成交。
- 卖出积木成交。
- 止盈成交。
- 止损成交。
- 移动止损成交。
- 清仓成交。
- 回测结束自动清仓成交。

推荐显示：

- `买入成交` 或 `卖出成交`
- 成交价格
- 成交数量
- 触发积木名称
- 成交原因

### `ORDER_BLOCKED`

表示策略产生交易意图，但市场规则不允许成交。

适用场景：

- A 股 T+1 导致当日买入持仓不可卖出。
- 后续扩展：涨跌停、最小交易单位、可卖数量不足等。

推荐显示：

- `卖出信号被拦截`
- 拦截原因
- 市场规则
- 原计划数量和价格

### `COOLDOWN_STARTED`

表示策略进入冷却。

适用场景：

- 止损成交后，冷却积木开始生效。
- 后续扩展：用户定义异常情况触发冷却。

推荐显示：

- `进入冷却`
- 冷却 K 线数
- 触发原因
- 触发积木名称

### `POSITION_CLOSED`

表示持仓被关闭。

适用场景：

- 清仓积木触发后持仓归零。
- 回测结束自动清仓。

为了避免和 `TRADE_FILLED` 重复，本阶段只在“持仓归零”这个状态变化值得强调时记录。前端文案可以显示为 `持仓已关闭`，说明由哪次成交导致。

## 数据结构

后端新增 schema：`BacktestTimelineItem`。

字段：

- `id`: 字符串，前端列表 key。
- `time`: 字符串，沿用当前 K 线时间格式。
- `eventType`: `TRADE_FILLED`、`ORDER_BLOCKED`、`COOLDOWN_STARTED`、`POSITION_CLOSED`。
- `title`: 前端主标题，例如 `买入成交`。
- `description`: 解释文案，例如 `买入积木触发，按当前 K 线收盘价成交`。
- `severity`: `info`、`success`、`warning`、`danger`。
- `side`: 可选，`BUY` 或 `SELL`。
- `price`: 可选，成交价或计划成交价。
- `quantity`: 可选，成交数量或计划数量。
- `rule`: 可选，例如 `T+1`。
- `nodeId`: 可选，触发积木节点 id。
- `nodeType`: 可选，触发积木类型。
- `nodeLabel`: 可选，触发积木名称。
- `details`: 可选，存放冷却 K 线数、退出规则类型等扩展信息。

`BacktestRunResponse` 和 `BacktestRecordDetailResponse` 新增：

- `timeline: list[BacktestTimelineItem]`

兼容规则：

- 新数据必须写入 `timeline`。
- 旧数据没有 `timeline` 时，前端按空数组处理。
- 现有 `events` 字段暂时保留，作为未成交原因的兼容字段。

## 数据库设计

新增表 `backtest_timeline_items`。

字段：

- `id`
- `task_id`
- `sequence`
- `item_id`
- `item_time`
- `event_type`
- `title`
- `description`
- `severity`
- `side`
- `price`
- `quantity`
- `rule`
- `node_id`
- `node_type`
- `node_label`
- `details_json`

约束：

- `task_id` 外键关联 `backtest_tasks.id`。
- 删除回测任务时级联删除时间线。
- 按 `sequence` 排序返回。

## 后端实现思路

### 回测引擎

`run_backtest_with_candles()` 内维护：

- `trades`
- `events`
- `timeline`
- `equity_curve`

在以下节点追加时间线：

1. 买入成交后追加 `TRADE_FILLED`。
2. 卖出成交后追加 `TRADE_FILLED`。
3. A 股 T+1 拦截后追加 `ORDER_BLOCKED`，同时继续写入当前 `events`。
4. 止损成交且冷却积木存在时追加 `COOLDOWN_STARTED`。
5. 持仓变为 0 且关闭原因是清仓积木或回测结束自动清仓时，追加 `POSITION_CLOSED`。止盈、止损、移动止损导致的持仓归零由对应的 `TRADE_FILLED` 解释，本阶段不额外追加 `POSITION_CLOSED`。

### 保存和读取

`save_backtest_result()`：

- 保存 `trades`。
- 保存 `events`。
- 保存 `timeline`。
- 保存 `equityCurve`。

`get_backtest_record()`：

- 返回 `timeline`。
- 如果数据库里没有时间线，返回空数组。

## 前端实现思路

### 搭建页

`BacktestRunResult` 增加 `timeline` 类型。

回测结果卡片新增区域：

- class: `backtest-timeline`
- 标题：`策略执行时间线`
- 右侧显示事件数量。

每条时间线记录：

- 左侧小圆点或短线，按 severity 上色。
- 主标题显示 `title`。
- 副文案显示 `description`。
- meta 行显示时间、触发积木、价格、数量、规则。

### 个人空间

`BacktestDetail` 增加 `timeline` 类型。

详情面板复用同一套 CSS class，保证视觉一致。

旧数据兼容：

- `selectedBacktest.timeline?.length` 判断。
- 没有 timeline 时不显示该区域。

## 测试策略

### 后端测试

新增或扩展：

- 买入 + 止盈成交时返回 `TRADE_FILLED`。
- A 股 T+1 拦截时返回 `ORDER_BLOCKED`。
- 止损 + 冷却时返回 `COOLDOWN_STARTED`。
- 保存回测后，详情接口返回和运行接口一致的 `timeline`。

### 前端测试

扩展：

- 搭建页回测结果显示“策略执行时间线”。
- 搭建页显示成交、规则拦截、冷却文案。
- 个人空间回测详情显示“策略执行时间线”。
- 没有 timeline 的旧回测详情不会报错。

## 验收标准

- 用户运行回测后，可以看到一条按时间排序的执行时间线。
- 时间线能解释买入、卖出、止盈、止损、移动止损、冷却、清仓和规则拦截中的关键事件。
- A 股 T+1 被拦截的卖出信号同时出现在 `events` 和 `timeline`。
- 保存后的回测在个人空间中仍能看到同样的时间线。
- 现有成交表、规则提示和权益曲线不被破坏。
- 后端测试、前端测试和前端构建通过。

## 后续扩展

后续可以在本设计上继续扩展：

- 手续费、印花税、佣金。
- 滑点和成交价偏移。
- 涨跌停拦截。
- 美股盘前盘后规则。
- 逐 K 线持仓状态。
- 回测报告下载。
- 时间线筛选和导出。
