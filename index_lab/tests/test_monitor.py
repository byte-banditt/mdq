import pandas as pd
import pytest
from indexkit.data import config, load, prices
from indexkit.index_engine import build
from indexkit.monitor import monitor, rebalance_report


@pytest.fixture
def state():
    c = config()
    f, _ = load(c)
    p = prices(f, c)
    r = build(p, "MOM10", c)
    return c, f, p, r


@pytest.mark.parametrize(
    "fault,check",
    [
        ("zero", "non_positive_price"),
        ("duplicate", "duplicate_rows"),
        ("missing", "missing_constituent_price"),
        ("jump", "overnight_jump"),
    ],
)
def test_faults(state, fault, check):
    c, f, p, r = state
    day = r.weights.index[10]
    symbol = r.weights.loc[day].idxmax()
    i = f.index[(f.symbol == symbol) & (f.date == day)][0]
    bad = f.copy()
    if fault == "zero":
        bad.loc[i, ["open", "close", "adj_close"]] = 0
    if fault == "duplicate":
        bad = pd.concat([bad, bad.loc[[i]]], ignore_index=True)
    if fault == "missing":
        bad = bad.drop(i)
    if fault == "jump":
        bad.loc[i, "adj_close"] *= 1.5
    log = monitor(bad, p, {"MOM10": r}, c)
    assert check in set(log.check_name)
    with pytest.raises(ValueError):
        prices(bad, c)


def test_rebalance(state):
    c, f, p, r = state
    log = monitor(f, p, {"MOM10": r}, c)
    proposal = rebalance_report(r, p, c, log)
    assert proposal.groupby("effective_date").after.sum().eq(1).all()
    assert len(proposal) == len(r.turnover) * len(p.columns)
    assert proposal.groupby("effective_date").trade.apply(
        lambda x: x.abs().sum()
    ).to_numpy() == pytest.approx(r.turnover.turnover.to_numpy())


def test_proposal_sanity_review(state):
    from copy import deepcopy

    c, f, p, r = state
    c = deepcopy(c)
    c["thresholds"]["turnover"] = 0.01
    log = monitor(f, p, {"MOM10": r}, c)
    proposal = rebalance_report(r, p, c, log)
    assert "rebalance_turnover" in proposal.checks.iloc[0]
