"""Close decisions, next-session execution, drifted holdings and explicit costs."""

from copy import deepcopy
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .calendar import rebalances


@dataclass
class IndexResult:
    name: str
    levels: pd.DataFrame
    weights: pd.DataFrame
    turnover: pd.DataFrame
    changes: pd.DataFrame
    contributions: pd.DataFrame


class BaseIndex:
    def __init__(self, name, cfg):
        self.name, self.cfg = name, cfg
        self.n = cfg["indices"][name]["n"]
        if not isinstance(self.n, int) or not 1 <= self.n <= len(cfg["universe"]):
            raise ValueError("Constituent count outside universe")
        if not np.isfinite(cfg["cost_bps"]) or cfg["cost_bps"] < 0:
            raise ValueError("Cost must be finite and nonnegative")

    def select(self, history):
        raise NotImplementedError

    def weight(self, selected, columns):
        w = pd.Series(0.0, index=columns)
        w.loc[selected] = 1 / len(selected)
        return w

    def rebalance(self, history):
        selected = self.select(history)
        if len(selected) != self.n:
            raise ValueError("Insufficient eligible full-history names")
        return self.weight(selected, history.columns)


class MomentumIndex(BaseIndex):
    def select(self, history):
        day = history.index[-1]
        start = day - pd.DateOffset(months=self.cfg["momentum_months"])
        end = day - pd.DateOffset(months=self.cfg["skip_months"])
        if history.index[0] > start:
            return []
        scores = history.loc[:end].iloc[-1] / history.loc[:start].iloc[-1] - 1
        return (
            scores.sort_index()
            .sort_values(ascending=False, kind="stable")
            .head(self.n)
            .index.tolist()
        )


class LowVolIndex(BaseIndex):
    def select(self, history):
        n = self.cfg["vol_days"]
        if len(history) < n + 1:
            return []
        scores = history.pct_change(fill_method=None).iloc[-n:].std(ddof=1) * np.sqrt(
            self.cfg["annual_sessions"]
        )
        return scores.sort_index().sort_values(kind="stable").head(self.n).index.tolist()


def build(panel, name, cfg):
    if panel.index.has_duplicates or not panel.index.is_monotonic_increasing:
        raise ValueError("Duplicate/out-of-order dates")
    if not np.isfinite(panel.to_numpy()).all() or (panel <= 0).any().any():
        raise ValueError("Invalid constituent price")
    returns = panel.pct_change(fill_method=None)
    if (returns.abs() > cfg["thresholds"]["stock_jump"]).any().any():
        raise ValueError("Overnight jump")
    rule = cfg["indices"][name]["rule"]
    if rule not in {"momentum", "low_vol"}:
        raise ValueError("Unknown index rule")
    engine = (MomentumIndex if rule == "momentum" else LowVolIndex)(name, cfg)
    # Both indices start together after momentum warmup for comparable reporting.
    warmup = panel.index[0] + pd.DateOffset(months=cfg["momentum_months"])
    schedule = {eff: decision for decision, eff in rebalances(panel.index) if decision >= warmup}
    if not schedule:
        raise ValueError("Insufficient history for first rebalance")
    base_date = min(schedule.values())
    w = pd.Series(0.0, index=panel.columns)
    net = gross = cfg["base_level"]
    rows = [
        dict(date=base_date, level=net, gross_level=gross, return_=0.0, gross_return=0.0, cost=0.0)
    ]
    weights = []
    contributions = []
    turns = []
    changes = []
    for day in panel.index[panel.index > base_date]:
        cost = 0.0
        if day in schedule:
            decision = schedule[day]
            target = engine.rebalance(panel.loc[:decision])
            traded = (target - w).abs().sum()  # purchases + sales, charge each side once
            cost = traded * cfg["cost_bps"] / 10000 if cfg["net"] else 0.0
            if cost >= 1:
                raise ValueError("Cost consumes capital")
            turns.append(
                dict(
                    decision_date=decision,
                    effective_date=day,
                    turnover=traded,
                    cost=cost,
                    estimated_cost=traded * cfg["cost_bps"] / 10000,
                )
            )
            for symbol in panel.columns:
                if (w[symbol] > 0) != (target[symbol] > 0):
                    changes.append(
                        dict(
                            decision_date=decision,
                            effective_date=day,
                            symbol=symbol,
                            action="add" if target[symbol] > 0 else "remove",
                        )
                    )
            w = target
        weights.append(dict(date=day, **w.to_dict()))  # beginning-of-day weights
        c = w * returns.loc[day]
        g = c.sum()
        r = (1 - cost) * (1 + g) - 1
        gross *= 1 + g
        net *= 1 + r
        rows.append(
            dict(date=day, level=net, gross_level=gross, return_=r, gross_return=g, cost=cost)
        )
        contributions.append(dict(date=day, **c.to_dict()))
        w = w * (1 + returns.loc[day]) / (1 + g)
    return IndexResult(
        name,
        pd.DataFrame(rows).set_index("date"),
        pd.DataFrame(weights).set_index("date"),
        pd.DataFrame(turns),
        pd.DataFrame(changes, columns=["decision_date", "effective_date", "symbol", "action"]),
        pd.DataFrame(contributions).set_index("date"),
    )


def benchmark(panel, dates, cfg):
    if cfg["benchmark"] != "equal_weight_sample":
        raise ValueError("Benchmark not implemented")
    r = panel.pct_change(fill_method=None).reindex(dates)
    w = pd.Series(1 / len(panel.columns), index=panel.columns)
    values = [0.0]
    for i, day in enumerate(dates[1:], 1):
        if day.to_period("M") != dates[i - 1].to_period("M"):
            w[:] = 1 / len(w)
        ret = (w * r.loc[day]).sum()
        values.append(ret)
        w = w * (1 + r.loc[day]) / (1 + ret)
    returns = pd.Series(values, index=dates)
    return pd.DataFrame(
        {"return_": returns, "level": cfg["base_level"] * (1 + returns).cumprod()}, index=dates
    )


def metrics(levels, benchmark_returns, cfg):
    r = levels.return_.iloc[1:]
    b = benchmark_returns.reindex(r.index)
    n = len(r)
    years = (levels.index[-1] - levels.index[0]).days / 365.25
    ann = cfg["annual_sessions"]
    rf = (1 + cfg["risk_free"]) ** (1 / ann) - 1
    sd = r.std(ddof=1)
    active = r - b
    return dict(
        CAGR=(levels.level.iloc[-1] / levels.level.iloc[0]) ** (1 / years) - 1,
        vol=sd * np.sqrt(ann),
        Sharpe=(r.mean() - rf) / sd * np.sqrt(ann),
        max_drawdown=(levels.level / levels.level.cummax() - 1).min(),
        tracking_error=active.std(ddof=1) * np.sqrt(ann),
        information_ratio=active.mean() / active.std(ddof=1) * np.sqrt(ann)
        if active.std(ddof=1) > 0
        else np.nan,
        observations=n,
    )


def modification_demo(panel, name, cfg):
    scenarios = {"before": cfg}
    for label in ("cost_25bps", "top15", "universe_change"):
        changed = deepcopy(cfg)
        if label == "cost_25bps":
            changed["cost_bps"] = 25
        elif label == "top15":
            changed["indices"][name]["n"] = 15
        else:
            changed["universe"] = cfg["universe"][:-2]
        scenarios[label] = changed
    rows = []
    for label, c in scenarios.items():
        result = build(panel[c["universe"]], name, c)
        rows.append(
            dict(
                scenario=label,
                level=result.levels.level.iloc[-1],
                return_=result.levels.level.iloc[-1] / c["base_level"] - 1,
                vol=result.levels.return_.iloc[1:].std() * np.sqrt(c["annual_sessions"]),
                turnover=result.turnover.turnover.mean(),
            )
        )
    return pd.DataFrame(rows)
