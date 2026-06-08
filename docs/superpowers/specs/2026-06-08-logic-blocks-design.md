# Logic Blocks Design

Date: 2026-06-08

## Goal

Split boolean composition out of the `if` block. Users should build multi-condition strategies with explicit `与`, `或`, and `非` blocks, while `如果` remains a simple flow/condition gate.

## Scope

- Add a `逻辑` category to the builder block library.
- Add three builtin blocks: `与`, `或`, `非`.
- Remove the `条件组合` parameter from `如果`.
- Update the backtest engine so logic nodes participate in condition evaluation.
- Clear existing saved strategy, custom block, shared block, recommendation, and backtest records that may contain the old `if.params.mode` shape.

## Behavior

- `与`: passes only when every incoming condition passes.
- `或`: passes when at least one incoming condition passes.
- `非`: passes when the first incoming condition does not pass.
- `如果`: with no incoming condition passes by default; with incoming conditions, it acts as a simple gate. Users should use `与/或/非` when they need explicit boolean composition.
- Action nodes still require every directly connected condition node to pass. To express alternatives, users connect those alternatives into an `或` block first.

## Data Cleanup

The cleanup keeps users, roles, simulation accounts, forum posts, and forum comments. It clears records that either store old strategy graphs or point to old custom block graphs:

- `strategies`
- `custom_blocks`
- `shared_block_stats`
- `shared_block_favorites`
- `shared_block_imports`
- `recommendation_events`
- `backtest_tasks`
- `backtest_trades`
- `backtest_events`
- `backtest_timeline_items`
- `backtest_equity_points`

Forum posts are preserved, but old attachment fields are reset because they may point to deleted strategies, backtests, or custom blocks.

## Tests

- Backend engine tests cover `与`, `或`, and `非`.
- Frontend builder tests cover the new `逻辑` category, the three blocks, and the removed `条件组合` field.
