"""Daily oversight and proposed rebalance checks, with reusable mdq DQ."""

import pandas as pd

from .calendar import calendar_checks
from .data import quality


def monitor(frame, panel, results, cfg):
    issues = [quality(frame, cfg), calendar_checks(frame, cfg["universe"])]
    rows = []
    availability = frame.groupby(["date", "symbol"])[cfg["price_field"]].agg(["size", "count"])

    def flag(day, name, check, detail):
        rows.append(dict(date=day, symbol=name, check_name=check, severity="error", detail=detail))

    for name, result in results.items():
        issues.append(calendar_checks(frame, cfg["universe"], result.levels))
        for day, w in result.weights.iterrows():
            if abs(w.sum() - 1) > 1e-9:
                flag(day, name, "weight_sum", "Weights do not sum to one")
            for symbol in w[w > 0].index:
                status = (
                    availability.loc[(day, symbol)] if (day, symbol) in availability.index else None
                )
                if status is None or status["size"] != 1 or status["count"] != 1:
                    flag(day, symbol, "missing_constituent_price", "Required held price absent")
        r = result.levels.return_.iloc[1:]
        mean = r.shift().rolling(60, min_periods=60).mean()
        sd = r.shift().rolling(60, min_periods=60).std(ddof=1)
        for day in r.index[(r - mean).abs() > cfg["thresholds"]["index_sigma"] * sd]:
            flag(day, name, "index_return_outlier", "Daily return beyond trailing 4 sigma")
        for row in result.turnover.itertuples():
            w = result.weights.loc[row.effective_date]
            if row.turnover > cfg["thresholds"]["turnover"]:
                flag(row.effective_date, name, "rebalance_turnover", "Turnover above threshold")
            if (w > 0).sum() != cfg["indices"][name]["n"]:
                flag(row.effective_date, name, "rebalance_count", "Wrong constituent count")
            if w.max() > cfg["thresholds"]["weight_cap"]:
                flag(row.effective_date, name, "rebalance_cap", "Weight above cap")
    issues.append(
        pd.DataFrame(rows, columns=["date", "symbol", "check_name", "severity", "detail"])
    )
    return pd.concat(issues, ignore_index=True).drop_duplicates()


def rebalance_report(result, panel, cfg, exceptions):
    rows = []
    for event in result.turnover.itertuples():
        day = event.effective_date
        decision = event.decision_date
        target = result.weights.loc[day]
        if decision in result.weights.index:
            previous = result.weights.loc[decision]
            r = panel.pct_change(fill_method=None).loc[decision]
            before = previous * (1 + r) / (1 + (previous * r).sum())
        else:
            before = target * 0
        errors = exceptions[(exceptions.date == decision) & (exceptions.severity == "error")]
        reasons = sorted(set(errors.check_name))
        if event.turnover > cfg["thresholds"]["turnover"]:
            reasons.append("rebalance_turnover")
        if (target > 0).sum() != cfg["indices"][result.name]["n"]:
            reasons.append("rebalance_count")
        if target.max() > cfg["thresholds"]["weight_cap"]:
            reasons.append("rebalance_cap")
        if abs(target.sum() - 1) > 1e-9:
            reasons.append("weight_sum")
        checks = "PASS" if not reasons else "REVIEW: " + ", ".join(reasons)
        for symbol in target.index:
            rows.append(
                dict(
                    index=result.name,
                    decision_date=decision,
                    effective_date=day,
                    symbol=symbol,
                    before=before[symbol],
                    after=target[symbol],
                    trade=target[symbol] - before[symbol],
                    action="add"
                    if before[symbol] == 0 and target[symbol] > 0
                    else "remove"
                    if before[symbol] > 0 and target[symbol] == 0
                    else "retain",
                    turnover=event.turnover,
                    estimated_cost=event.estimated_cost,
                    checks=checks,
                )
            )
    return pd.DataFrame(rows)
