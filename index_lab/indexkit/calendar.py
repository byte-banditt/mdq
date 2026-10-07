"""Calendar inferred from observed prices; possible holidays remain warnings."""

import pandas as pd


def trading_days(frame):
    return pd.DatetimeIndex(sorted(pd.to_datetime(frame.date).unique()))


def rebalances(days):
    days = pd.DatetimeIndex(days)
    if days.has_duplicates or not days.is_monotonic_increasing:
        raise ValueError("Duplicate/out-of-order calendar")
    last = pd.Series(days, index=days).groupby(days.to_period("M")).last()
    return [(d, days[days.get_loc(d) + 1]) for d in last if days.get_loc(d) + 1 < len(days)]


def calendar_checks(frame, universe, levels=None):
    issues = []

    def add(d, name, detail):
        issues.append(
            dict(date=d, symbol="CALENDAR", check_name=name, severity="warning", detail=detail)
        )

    if frame.duplicated(["symbol", "date"]).any():
        add(pd.NaT, "calendar_duplicate", "Duplicate symbol/date")
    if not frame.groupby("symbol").date.apply(lambda x: x.is_monotonic_increasing).all():
        add(pd.NaT, "calendar_order", "Out-of-order dates per symbol")
    sub = frame[frame.symbol.isin(universe)]
    counts = sub.groupby("date").symbol.nunique()
    days = trading_days(sub)
    for day in pd.bdate_range(days.min(), days.max()):
        if counts.get(day, 0) <= len(universe) / 2:
            add(day, "calendar_possible_gap", "Weekday with most prices absent; may be holiday")
    if levels is not None:
        for d in levels.index.difference(days):
            add(d, "calendar_nontrading_level", "Level published on non-trading day")
        expected = days[(days >= levels.index.min()) & (days <= levels.index.max())]
        for d in expected.difference(levels.index):
            add(d, "calendar_missing_level", "Missing trading-day level")
    return pd.DataFrame(issues, columns=["date", "symbol", "check_name", "severity", "detail"])
