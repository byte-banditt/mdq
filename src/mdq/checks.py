"""Vectorized data-quality checks for daily OHLCV data."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

ISSUE_COLUMNS = ["symbol", "date", "check_name", "severity", "detail"]


def _issues(
    frame: pd.DataFrame, mask: pd.Series, name: str, severity: str, detail: str
) -> pd.DataFrame:
    found = frame.loc[mask, ["symbol", "date"]].copy()
    found["check_name"], found["severity"], found["detail"] = name, severity, detail
    return found[ISSUE_COLUMNS]


def check_non_positive_price(df: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    bad = df[["open", "high", "low", "close"]].isna().any(axis=1) | (
        df[["open", "high", "low", "close"]] <= 0
    ).any(axis=1)
    return _issues(df, bad, "non_positive_price", "error", "OHLC value null or <= 0")


def check_ohlc_inconsistent(df: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    bad = (df["low"] > df[["open", "close"]].min(axis=1)) | (
        df[["open", "close"]].max(axis=1) > df["high"]
    )
    return _issues(df, bad, "ohlc_inconsistent", "error", "Expected low <= open,close <= high")


def check_duplicate_rows(df: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    bad = df.duplicated(["symbol", "date"], keep=False)
    return _issues(
        df, bad, "duplicate_rows", "error", "Multiple downloaded rows for symbol/date"
    ).drop_duplicates(["symbol", "date"])


def check_missing_sessions(df: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    index_symbol = cfg.get("index_symbol", "^NSEI")
    calendar = set(df.loc[df.symbol == index_symbol, "date"])
    missing = []
    for symbol, group in df.groupby("symbol"):
        if symbol == index_symbol:
            continue
        absent = sorted(calendar - set(group.date))
        missing.extend({"symbol": symbol, "date": day} for day in absent)
    result = pd.DataFrame(missing, columns=["symbol", "date"])
    if result.empty:
        return pd.DataFrame(columns=ISSUE_COLUMNS)
    result["check_name"], result["severity"], result["detail"] = (
        "missing_sessions",
        "warning",
        "Date exists in index calendar but symbol row is absent",
    )
    return result[ISSUE_COLUMNS]


def check_stale_price(df: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    sessions = int(cfg.get("checks", {}).get("stale_sessions", 5))
    ordered = df.sort_values(["symbol", "date"]).copy()
    same = ordered.groupby("symbol")["close"].transform(lambda col: col.eq(col.shift()))
    groups = (~same).groupby(ordered["symbol"]).cumsum()
    streak = ordered.groupby(["symbol", groups]).cumcount() + 1
    mask = same & (streak >= sessions) & (ordered["volume"].fillna(0) > 0)
    return _issues(
        ordered,
        mask,
        "stale_price",
        "warning",
        f"Close unchanged for >= {sessions} sessions with volume > 0",
    )


def check_return_outlier(df: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    threshold = float(cfg.get("checks", {}).get("return_outlier_robust_z", 8.0))
    ordered = df.sort_values(["symbol", "date"]).copy()
    adjusted = pd.to_numeric(ordered["adj_close"], errors="coerce")
    returns = np.log(adjusted).groupby(ordered["symbol"]).diff()
    med = returns.groupby(ordered["symbol"]).transform("median")
    mad = (returns - med).abs().groupby(ordered["symbol"]).transform("median")
    score = (0.6745 * (returns - med) / mad.replace(0, np.nan)).abs()
    zero_mad_outlier = (mad == 0) & (returns.notna()) & (returns != med)
    return _issues(
        ordered,
        (score > threshold) | zero_mad_outlier,
        "return_outlier",
        "warning",
        f"Adjusted daily return robust z-score > {threshold}",
    )


def run_checks(
    conn: sqlite3.Connection,
    cfg: dict[str, Any],
    run_id: str,
    downloaded: pd.DataFrame | None = None,
) -> int:
    """Evaluate checks and append the complete issue set for this run."""
    frame = pd.read_sql_query("SELECT * FROM prices_raw", conn)
    if downloaded is not None and not downloaded.empty:
        frame = pd.concat([frame, downloaded], ignore_index=True)
    checks = [
        check_non_positive_price,
        check_ohlc_inconsistent,
        check_duplicate_rows,
        check_missing_sessions,
        check_stale_price,
        check_return_outlier,
    ]
    issues = pd.concat([fn(frame, cfg) for fn in checks], ignore_index=True)
    now = datetime.now(timezone.utc).isoformat()
    conn.executemany(
        "INSERT OR REPLACE INTO dq_issues("
        "run_id,symbol,date,check_name,severity,detail,detected_at) "
        "VALUES(?,?,?,?,?,?,?)",
        [
            (run_id, r.symbol, r.date, r.check_name, r.severity, r.detail, now)
            for r in issues.itertuples(index=False)
        ],
    )
    return len(issues)
