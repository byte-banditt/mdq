"""Monthly Brinson-Fachler on gross holdings; explicit cost/compounding bridge."""

import numpy as np
import pandas as pd


def brinson(result, panel, bench, sectors):
    returns = panel.pct_change(fill_method=None)
    rows = []
    periods = []
    for period, weights in result.weights.groupby(result.weights.index.to_period("M")):
        dates = weights.index
        wp = weights.iloc[0]
        wb = pd.Series(1 / len(wp), index=wp.index)
        stock = (1 + returns.loc[dates]).prod() - 1
        rp = (wp * stock).sum()
        rb = (wb * stock).sum()
        actual = (1 + result.levels.loc[dates, "gross_return"]).prod() - 1
        observed_b = (1 + bench.loc[dates, "return_"]).prod() - 1
        if not np.isclose(rp, actual, atol=1e-11) or not np.isclose(rb, observed_b, atol=1e-11):
            raise ValueError("Monthly holdings assumptions do not reconcile")
        for sector in sorted(set(sectors.values())):
            names = [s for s in wp.index if sectors[s] == sector]
            ps = wp[names].sum()
            bs = wb[names].sum()
            rbs = (wb[names] * stock[names]).sum() / bs
            rps = (wp[names] * stock[names]).sum() / ps if ps > 0 else rbs
            allocation = (ps - bs) * (rbs - rb)
            selection = bs * (rps - rbs)
            interaction = (ps - bs) * (rps - rbs)
            rows.append(
                dict(
                    index=result.name,
                    month=str(period),
                    sector=sector,
                    w_p=ps,
                    w_b=bs,
                    R_p=rps,
                    R_b=rbs,
                    allocation=allocation,
                    selection=selection,
                    interaction=interaction,
                )
            )
        net = (1 + result.levels.loc[dates, "return_"]).prod() - 1
        periods.append(
            dict(
                index=result.name,
                month=str(period),
                portfolio_gross=rp,
                portfolio_net=net,
                benchmark=rb,
                active_gross=rp - rb,
                cost_effect=net - rp,
                active_net=net - rb,
            )
        )
    attribution = pd.DataFrame(rows)
    monthly = pd.DataFrame(periods)
    arithmetic = monthly.active_gross.sum()
    compounded = (1 + monthly.portfolio_gross).prod() - (1 + monthly.benchmark).prod()
    bridge = pd.DataFrame(
        [
            dict(
                index=result.name,
                arithmetic_active=arithmetic,
                compounded_active=compounded,
                compounding_residual=compounded - arithmetic,
                total_cost_effect=(1 + monthly.portfolio_net).prod()
                - (1 + monthly.portfolio_gross).prod(),
            )
        ]
    )
    return attribution, monthly, bridge


def contributors(result):
    previous_wealth = (
        (1 + result.levels.gross_return).cumprod().shift().reindex(result.contributions.index)
    )
    totals = result.contributions.mul(previous_wealth, axis=0).sum().sort_values(ascending=False)
    rows = []
    for label, part in [("top5", totals.head(5)), ("bottom5", totals.tail(5))]:
        for symbol, value in part.items():
            rows.append(dict(index=result.name, group=label, symbol=symbol, contribution=value))
    return pd.DataFrame(rows)
