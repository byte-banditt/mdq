import copy

import numpy as np
import pandas as pd
import pytest
from indexkit.calendar import calendar_checks, rebalances
from indexkit.data import config, load, prices, quality
from indexkit.index_engine import benchmark, build, modification_demo


def sample():
    c = config()
    days = pd.bdate_range("2020-01-01", periods=420)
    p = pd.DataFrame(
        100 * np.exp(np.arange(len(days))[:, None] * np.linspace(0.0001, 0.001, 20)),
        index=days,
        columns=c["universe"],
    )
    return c, p


def test_calendar():
    days = pd.to_datetime(["2024-01-30", "2024-01-31", "2024-02-02", "2024-02-29"])
    assert rebalances(days) == [(days[1], days[2])]
    f = pd.DataFrame({"symbol": ["X"] * len(days), "date": days})
    assert "calendar_possible_gap" in set(calendar_checks(f, ["X"]).check_name)
    with pytest.raises(ValueError):
        rebalances(days[::-1])


def test_no_future_and_reconciliation():
    c, p = sample()
    a = build(p, "MOM10", c)
    effective = a.turnover.effective_date.iloc[0]
    altered = p.copy()
    altered.loc[effective:, p.columns[0]] *= 1.09
    altered.loc[effective:, p.columns[-1]] *= 0.91
    b = build(altered, "MOM10", c)
    pd.testing.assert_series_equal(a.weights.loc[effective], b.weights.loc[effective])
    assert a.weights.iloc[0].sum() == pytest.approx(1)
    np.testing.assert_allclose(a.contributions.sum(axis=1), a.levels.gross_return.iloc[1:])
    assert a.turnover.turnover.iloc[0] == pytest.approx(1)
    assert (a.levels.level <= a.levels.gross_level + 1e-9).all()
    for row in a.turnover.itertuples():
        assert row.effective_date > row.decision_date


def test_cost_and_drift():
    c, p = sample()
    a = build(p, "LVOL10", c)
    date = a.weights.index[1]
    previous = a.weights.index[0]
    r = p.pct_change(fill_method=None).loc[previous]
    np.testing.assert_allclose(
        a.weights.loc[date],
        a.weights.loc[previous] * (1 + r) / (1 + (a.weights.loc[previous] * r).sum()),
    )
    c0 = copy.deepcopy(c)
    c0["net"] = False
    b = build(p, "LVOL10", c0)
    np.testing.assert_allclose(b.levels.level, b.levels.gross_level)
    demo = modification_demo(p, "MOM10", c)
    assert demo.loc[1, "level"] < demo.loc[0, "level"]
    assert len(benchmark(p, a.levels.index, c)) == len(a.levels)


def test_data_and_mdq_reuse():
    c = config()
    f, _ = load(c)
    assert "overnight_jump" in set(quality(f, c).check_name)
    assert len(prices(f, c).columns) == 20
    bad = f.copy()
    i = bad.index[bad.symbol == c["universe"][0]][0]
    bad.loc[i, "adj_close"] = 0
    with pytest.raises(ValueError):
        prices(bad, c)
