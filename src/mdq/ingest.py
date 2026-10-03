"""Market-data download, incremental loading, and run orchestration."""

from __future__ import annotations

import logging
import sqlite3
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pandas as pd
import yfinance as yf

from mdq.store import connect

LOGGER = logging.getLogger("mdq")


def download_prices(symbols: list[str], start: str, end: str) -> pd.DataFrame:
    """Download one batch; retry transient source failures with bounded backoff."""
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            frame = yf.download(
                symbols,
                start=start,
                end=end,
                auto_adjust=False,
                progress=False,
                threads=False,
                group_by="ticker",
                actions=False,
            )
            if frame.empty:
                raise RuntimeError("yfinance returned no rows")
            rows = []
            for symbol in symbols:
                try:
                    if isinstance(frame.columns, pd.MultiIndex):
                        part = frame[symbol].copy()
                    else:
                        part = frame.copy()
                except KeyError:
                    continue
                part.columns = [str(column).lower().replace(" ", "_") for column in part.columns]
                part["symbol"] = symbol
                part["date"] = pd.to_datetime(part.index).date.astype(str)
                rows.append(part.reset_index(drop=True))
            returned = {row["symbol"].iloc[0] for row in rows}
            missing = set(symbols) - returned
            if missing:
                raise RuntimeError(f"yfinance omitted requested symbols: {sorted(missing)}")
            if not rows:
                raise RuntimeError("yfinance returned no requested symbols")
            result = pd.concat(rows, ignore_index=True)
            null_symbols = result.groupby("symbol")[["open", "high", "low", "close"]].apply(
                lambda values: values.isna().all().all()
            )
            if null_symbols.any():
                raise RuntimeError(
                    "yfinance returned only null OHLC for: "
                    f"{null_symbols[null_symbols].index.tolist()}"
                )
            if "adj_close" not in result:
                result["adj_close"] = result.get("close")
            return result[["symbol", "date", "open", "high", "low", "close", "adj_close", "volume"]]
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2**attempt)
    raise RuntimeError(f"yfinance download failed after 3 attempts: {last_error}") from last_error


def _date_window(cfg: dict[str, Any], database: str, full: bool) -> tuple[str, str]:
    end = cfg.get("end_date") or date.today().isoformat()
    start = cfg["start_date"]
    if not full:
        with connect(database) as conn:
            latest = conn.execute("SELECT MAX(date) FROM prices_raw").fetchone()[0]
        if latest:
            overlap = int(cfg.get("overlap_days", 5))
            start = max(start, (date.fromisoformat(latest) - timedelta(days=overlap)).isoformat())
    return start, end


def upsert_prices(conn: sqlite3.Connection, frame: pd.DataFrame, ingested_at: str) -> int:
    """Upsert source rows; primary key makes retries and overlap safe."""
    sql = """INSERT INTO prices_raw(symbol,date,open,high,low,close,adj_close,volume,ingested_at)
    VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(symbol,date) DO UPDATE SET
    open=excluded.open,high=excluded.high,low=excluded.low,close=excluded.close,
    adj_close=excluded.adj_close,volume=excluded.volume,ingested_at=excluded.ingested_at
    WHERE prices_raw.open IS NOT excluded.open OR prices_raw.high IS NOT excluded.high
    OR prices_raw.low IS NOT excluded.low OR prices_raw.close IS NOT excluded.close
    OR prices_raw.adj_close IS NOT excluded.adj_close OR prices_raw.volume IS NOT excluded.volume"""
    values = [
        (
            r.symbol,
            r.date,
            _number(r.open),
            _number(r.high),
            _number(r.low),
            _number(r.close),
            _number(r.adj_close),
            _number(r.volume),
            ingested_at,
        )
        for r in frame.itertuples(index=False)
    ]
    conn.executemany(sql, values)
    return len(values)


def _number(value: Any) -> float | None:
    return None if pd.isna(value) else float(value)


def run_pipeline(cfg: dict[str, Any], full: bool = False) -> None:
    """Run ingest and downstream stages under one auditable run id."""
    from mdq.checks import run_checks
    from mdq.clean import rebuild_clean
    from mdq.report import export_excel, write_results

    run_id = str(uuid.uuid4())
    started = datetime.now(timezone.utc).isoformat()
    database = cfg["database"]
    LOGGER.info("run_id=%s status=started", run_id)
    with connect(database) as conn:
        conn.execute(
            "INSERT INTO runs(run_id,started_at,status) VALUES(?,?,'running')",
            (run_id, started),
        )
    try:
        start, end = _date_window(cfg, database, full)
        prices = download_prices(cfg["symbols"], start, end)
        with connect(database) as conn:
            count = upsert_prices(conn, prices, datetime.now(timezone.utc).isoformat())
            issues = run_checks(conn, cfg, run_id, downloaded=prices)
            rebuild_clean(conn, run_id)
            conn.execute(
                "UPDATE runs SET rows_ingested=?, issues_found=? WHERE run_id=?",
                (count, issues, run_id),
            )
        export_excel(database, run_id)
        write_results(database, cfg, run_id, started)
        with connect(database) as conn:
            conn.execute(
                "UPDATE runs SET status='success',finished_at=? WHERE run_id=?",
                (datetime.now(timezone.utc).isoformat(), run_id),
            )
        LOGGER.info("run_id=%s status=success rows=%s issues=%s", run_id, count, issues)
    except Exception:
        with connect(database) as conn:
            conn.execute(
                "UPDATE runs SET status='failed',finished_at=? WHERE run_id=?",
                (datetime.now(timezone.utc).isoformat(), run_id),
            )
        LOGGER.exception("run_id=%s status=failed", run_id)
        raise
