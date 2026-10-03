import pandas as pd
import pytest

from mdq import ingest
from mdq.ingest import upsert_prices
from mdq.store import connect, init_db


def test_fixture_upsert_is_idempotent(tmp_path, prices_frame):
    db = str(tmp_path / "test.sqlite")
    init_db(db)
    frame = prices_frame
    with connect(db) as conn:
        assert upsert_prices(conn, frame, "2024-01-03T00:00:00Z") == 3
        assert upsert_prices(conn, frame, "2024-01-03T00:00:00Z") == 3
        before = conn.execute("SELECT * FROM prices_raw ORDER BY symbol,date").fetchall()
        assert upsert_prices(conn, frame, "2024-01-04T00:00:00Z") == 3
        after = conn.execute("SELECT * FROM prices_raw ORDER BY symbol,date").fetchall()
        assert before == after
        assert conn.execute("SELECT COUNT(*) FROM prices_raw").fetchone()[0] == 3


def test_upsert_changed_value_is_updated(prices_frame, tmp_path):
    db = str(tmp_path / "changed.sqlite")
    init_db(db)
    with connect(db) as conn:
        upsert_prices(conn, prices_frame, "2024-01-03T00:00:00Z")
        changed = prices_frame.copy()
        changed.loc[0, "close"] = 13
        upsert_prices(conn, changed, "2024-01-04T00:00:00Z")
        row = conn.execute(
            "SELECT close,ingested_at FROM prices_raw WHERE symbol='AAA.NS' AND date='2024-01-01'"
        ).fetchone()
        assert row["close"] == 13
        assert row["ingested_at"] == "2024-01-04T00:00:00Z"
        assert conn.execute("SELECT COUNT(*) FROM prices_raw").fetchone()[0] == 3


def test_date_window_incremental_full_and_empty_database(tmp_path, prices_frame):
    from mdq.ingest import _date_window

    db = str(tmp_path / "window.sqlite")
    init_db(db)
    cfg = {
        "database": db,
        "start_date": "2020-01-01",
        "end_date": "2024-06-01",
        "overlap_days": 7,
    }
    assert _date_window(cfg, db, full=False) == ("2020-01-01", "2024-06-01")
    with connect(db) as conn:
        upsert_prices(conn, prices_frame, "2024-01-03T00:00:00Z")
    assert _date_window(cfg, db, full=False) == ("2023-12-26", "2024-06-01")
    assert _date_window(cfg, db, full=True) == ("2020-01-01", "2024-06-01")


def _yfinance_frame(symbols, null_ohlc=False):
    fields = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    values = [None] * len(fields) if null_ohlc else [10, 11, 9, 10, 10, 100]
    columns = pd.MultiIndex.from_product([symbols, fields])
    return pd.DataFrame(
        [[value for _ in symbols for value in values]],
        index=pd.to_datetime(["2024-01-02"]),
        columns=columns,
    )


def test_download_retries_twice_then_succeeds(monkeypatch):
    responses = [RuntimeError("temporary"), RuntimeError("temporary"), _yfinance_frame(["AAA.NS"])]
    calls = []
    sleeps = []

    def fake_download(*args, **kwargs):
        calls.append(kwargs)
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(ingest.yf, "download", fake_download)
    monkeypatch.setattr(ingest.time, "sleep", sleeps.append)
    result = ingest.download_prices(["AAA.NS"], "2024-01-01", "2024-01-03")

    assert len(calls) == 3
    assert sleeps == [1, 2]
    assert result[["symbol", "date"]].values.tolist() == [["AAA.NS", "2024-01-02"]]


def test_download_failure_after_three_attempts_raises(monkeypatch):
    calls = []

    def fail(*args, **kwargs):
        calls.append(True)
        raise RuntimeError("offline")

    monkeypatch.setattr(ingest.yf, "download", fail)
    monkeypatch.setattr(ingest.time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="failed after 3 attempts"):
        ingest.download_prices(["AAA.NS"], "2024-01-01", "2024-01-03")
    assert len(calls) == 3


def test_download_omitted_symbol_raises(monkeypatch):
    monkeypatch.setattr(ingest.yf, "download", lambda *a, **k: _yfinance_frame(["AAA.NS"]))
    monkeypatch.setattr(ingest.time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="omitted requested symbols"):
        ingest.download_prices(["AAA.NS", "BBB.NS"], "2024-01-01", "2024-01-03")


def test_download_all_null_ohlc_symbol_raises(monkeypatch):
    monkeypatch.setattr(
        ingest.yf, "download", lambda *a, **k: _yfinance_frame(["AAA.NS"], null_ohlc=True)
    )
    monkeypatch.setattr(ingest.time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="only null OHLC"):
        ingest.download_prices(["AAA.NS"], "2024-01-01", "2024-01-03")
