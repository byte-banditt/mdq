"""Read existing mdq storage; reuse its checks without mutating source DB."""

import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from mdq import checks

ROOT = Path(__file__).resolve().parents[1]


def config():
    return json.loads((ROOT / "config.yaml").read_text())


def load(cfg):
    database = (ROOT / cfg["database"]).resolve()
    if not database.exists():
        raise FileNotFoundError(database)
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as conn:
        table = cfg["price_table"]
        if table not in {"prices_raw", "prices_clean"}:
            raise ValueError("Unsupported price table")
        frame = pd.read_sql_query(f"SELECT * FROM {table} ORDER BY date,symbol", conn)
        schema = pd.read_sql_query("SELECT name,sql FROM sqlite_master WHERE type='table'", conn)
    frame["date"] = pd.to_datetime(frame.date)
    audit = (
        schema.to_string(index=False)
        + "\n"
        + frame.groupby("symbol")
        .agg(rows=("date", "size"), start=("date", "min"), end=("date", "max"))
        .to_string()
        + "\nNull counts:\n"
        + frame.isna().sum().to_string()
    )
    return frame, audit


def quality(frame, cfg):
    legacy = dict(
        cfg, symbols=cfg["universe"], checks={"stale_sessions": cfg["thresholds"]["stale_sessions"]}
    )
    functions = [
        checks.check_non_positive_price,
        checks.check_ohlc_inconsistent,
        checks.check_duplicate_rows,
        checks.check_missing_sessions,
        checks.check_stale_price,
        checks.check_return_outlier,
    ]
    with np.errstate(divide="ignore", invalid="ignore"):
        found = [fn(frame, legacy) for fn in functions]
    invalid = frame.loc[
        ~np.isfinite(frame[cfg["price_field"]]) | (frame[cfg["price_field"]] <= 0),
        ["symbol", "date"],
    ].copy()
    invalid["check_name"], invalid["severity"], invalid["detail"] = (
        "invalid_calculation_price",
        "error",
        "Calculation price null or non-positive",
    )
    found.append(invalid)
    ordered = frame.sort_values(["symbol", "date"])
    returns = ordered.groupby("symbol")[cfg["price_field"]].pct_change(fill_method=None)
    jump = ordered.loc[returns.abs() > cfg["thresholds"]["stock_jump"], ["symbol", "date"]].copy()
    jump["check_name"], jump["severity"], jump["detail"] = (
        "overnight_jump",
        "error",
        "Adjusted return beyond +/-20%; review corporate action",
    )
    found.append(jump)
    return pd.concat(found, ignore_index=True)


def prices(frame, cfg):
    selected = frame[frame.symbol.isin(cfg["universe"])].copy()
    if selected.duplicated(["symbol", "date"]).any():
        raise ValueError("Duplicate symbol/date")
    if not selected.groupby("symbol").date.apply(lambda x: x.is_monotonic_increasing).all():
        raise ValueError("Out-of-order dates")
    panel = selected.pivot(index="date", columns="symbol", values=cfg["price_field"])
    panel = panel.reindex(columns=cfg["universe"])
    if cfg.get("start"):
        panel = panel.loc[cfg["start"] :]
    if cfg.get("end"):
        panel = panel.loc[: cfg["end"]]
    if panel.empty or not np.isfinite(panel.to_numpy()).all() or (panel <= 0).any().any():
        raise ValueError("Missing/non-positive constituent prices; calculation blocked")
    if (panel.pct_change(fill_method=None).abs() > cfg["thresholds"]["stock_jump"]).any().any():
        raise ValueError("Overnight jump; calculation blocked pending review")
    return panel
