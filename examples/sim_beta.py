"""Estimate a single-index model from clean prices and report raw/clean differences."""

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from mdq.store import connect

DB = Path("data/mdq.sqlite")


def returns(conn: sqlite3.Connection, table: str, symbol: str) -> pd.Series:
    frame = pd.read_sql_query(
        f"SELECT date,adj_close FROM {table} WHERE symbol=? ORDER BY date",
        conn,
        params=(symbol,),
    )
    frame["date"] = pd.to_datetime(frame["date"])
    series = frame.set_index("date")["adj_close"].pct_change()
    return series.replace([np.inf, -np.inf], np.nan).dropna()


def fit(stock: pd.Series, market: pd.Series) -> tuple[float, float, float] | None:
    joined = pd.concat([stock.rename("stock"), market.rename("market")], axis=1).dropna()
    if len(joined) < 3:
        return None
    design = np.column_stack([np.ones(len(joined)), joined["market"]])
    alpha, beta = np.linalg.lstsq(design, joined["stock"], rcond=None)[0]
    residual = joined["stock"] - design @ np.array([alpha, beta])
    return float(alpha), float(beta), float(np.var(residual, ddof=2))


def main() -> None:
    if not DB.exists():
        raise SystemExit("Run mdq run first to populate data/mdq.sqlite")
    with connect(str(DB)) as conn:
        market = returns(conn, "prices_clean", "^NSEI")
        symbols = [
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT symbol FROM prices_clean WHERE symbol != '^NSEI' ORDER BY symbol"
            )
        ]
        for symbol in symbols:
            clean_fit = fit(returns(conn, "prices_clean", symbol), market)
            raw_fit = fit(returns(conn, "prices_raw", symbol), returns(conn, "prices_raw", "^NSEI"))
            print(f"{symbol}: clean alpha,beta,resid_var={clean_fit}")
            if (
                raw_fit is not None
                and clean_fit is not None
                and not np.allclose(raw_fit, clean_fit, equal_nan=True)
            ):
                print(f"  measured raw-clean difference: raw={raw_fit}; clean={clean_fit}")
            elif raw_fit is not None and clean_fit is not None:
                print("  raw and clean estimates equal")


if __name__ == "__main__":
    main()
