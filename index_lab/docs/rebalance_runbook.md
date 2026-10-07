# Rebalance runbook

1. Check source DQ, adjustment warnings, duplicates and calendar; confirm constituent membership.
2. Run calculation at the decision close, using only that close and earlier data.
3. Review monitor exceptions and proposed adds/removes, drifted weights, turnover and estimated cost.
4. Record human approval, reviewer and timestamp; no automatic approval is implied.
5. Publish approved description and targets effective the next trading session.
6. Verify realized positions, weight sum, realized costs and level reconciliation after rebalance.

The generated proposal is a backtest simulation, not evidence of approval or publication. Missing-weekday warnings require holiday/source review. Source warnings on excluded names remain visible.
