"""Deterministic clean-table rebuild and volatility comparison."""

import sqlite3

import numpy as np
import pandas as pd


def rebuild_clean(conn: sqlite3.Connection, run_id: str) -> int:
    """Replace clean prices using errors detected in this full-history run."""
    conn.execute("DELETE FROM prices_clean")
    conn.execute(
        """INSERT INTO prices_clean(symbol,date,open,high,low,close,adj_close,volume)
        SELECT symbol,date,open,high,low,close,adj_close,volume FROM prices_raw
        WHERE NOT EXISTS (
          SELECT 1 FROM dq_issues i WHERE i.run_id=? AND i.symbol=prices_raw.symbol
          AND i.date=prices_raw.date AND i.severity='error'
        )""",
        (run_id,),
    )
    return conn.execute("SELECT COUNT(*) FROM prices_clean").fetchone()[0]


def annualized_volatility(frame: pd.DataFrame) -> float:
    """Compute annualized volatility from close-to-close log returns."""
    ordered = frame.sort_values("date")
    close = pd.to_numeric(ordered["close"], errors="coerce")
    with np.errstate(divide="ignore", invalid="ignore"):
        returns = np.log(close).diff().dropna()
    if np.isinf(returns).any():
        return float("inf")
    return float(returns.std(ddof=1) * np.sqrt(252)) if len(returns) > 1 else float("nan")


def volatility_impact(conn: sqlite3.Connection, run_id: str) -> list[dict[str, float | str]]:
    """Compare raw and clean volatility for symbols with current-run errors."""
    symbols = [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT symbol FROM dq_issues WHERE run_id=? AND severity='error'", (run_id,)
        )
    ]
    results = []
    for symbol in symbols:
        raw = pd.read_sql_query(
            "SELECT date,close FROM prices_raw WHERE symbol=? ORDER BY date", conn, params=(symbol,)
        )
        clean = pd.read_sql_query(
            "SELECT date,close FROM prices_clean WHERE symbol=? ORDER BY date",
            conn,
            params=(symbol,),
        )
        raw_vol, clean_vol = annualized_volatility(raw), annualized_volatility(clean)
        ratio = raw_vol / clean_vol if np.isfinite(clean_vol) and clean_vol != 0 else float("nan")
        results.append(
            {
                "symbol": symbol,
                "raw_volatility": raw_vol,
                "clean_volatility": clean_vol,
                "ratio": ratio,
            }
        )
    return results
