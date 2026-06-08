# Logic Blocks Implementation Plan

Date: 2026-06-08

## Steps

1. Add failing backend tests for explicit `与`, `或`, and `非` condition nodes.
2. Add failing frontend tests for the `逻辑` category and `如果` parameter removal.
3. Update the backtest engine condition node set and recursive condition evaluation.
4. Update the builder block library definitions and category ordering.
5. Run focused backend and frontend tests to confirm the new behavior.
6. Clear old MySQL development records that store old strategy/custom block graphs.
7. Run full backend tests, full frontend tests, production build, and browser smoke verification.
8. Commit and push the project update to GitHub with a timestamped summary.
