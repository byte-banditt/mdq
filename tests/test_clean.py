import numpy as np
import pandas as pd

from mdq.checks import check_non_positive_price
from mdq.clean import annualized_volatility, rebuild_clean, volatility_impact
from mdq.store import connect, init_db


def test_clean_excludes_error_keeps_warning_and_computes_impact(tmp_path):
    db = str(tmp_path / "clean.sqlite")
    init_db(db)
    with connect(db) as conn:
        rows = [
            ("BAD.NS", "1", 10, 11, 9, 10, 10, 10, "now"),
            ("BAD.NS", "2", 0, 11, 0, 0, 0, 10, "now"),
            ("WARN.NS", "1", 10, 11, 9, 10, 10, 10, "now"),
        ]
        conn.executemany("INSERT INTO prices_raw VALUES(?,?,?,?,?,?,?,?,?)", rows)
        conn.executemany(
            "INSERT INTO dq_issues("
            "run_id,symbol,date,check_name,severity,detail,detected_at) "
            "VALUES(?,?,?,?,?,?,?)",
            [
                ("r1", "BAD.NS", "2", "non_positive_price", "error", "bad tick", "now"),
                ("r1", "WARN.NS", "1", "stale_price", "warning", "flat", "now"),
            ],
        )
        assert rebuild_clean(conn, "r1") == 2
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM prices_raw WHERE symbol='BAD.NS' AND date='2'"
            ).fetchone()[0]
            == 1
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM prices_clean WHERE symbol='BAD.NS' AND date='2'"
            ).fetchone()[0]
            == 0
        )
        assert (
            conn.execute("SELECT COUNT(*) FROM prices_clean WHERE symbol='WARN.NS'").fetchone()[0]
            == 1
        )
        impact = volatility_impact(conn, "r1")
        assert impact[0]["symbol"] == "BAD.NS"
        assert impact[0]["raw_volatility"] == float("inf")


def test_synthetic_zero_tick_volatility_is_undefined_until_rows_excluded():
    """Synthetic example: validate zero ticks are flagged and removed before volatility."""
    clean_close = [100 + i for i in range(12)]
    frame = pd.DataFrame(
        {
            "symbol": "SYNTH.NS",
            "date": [str(i) for i in range(12)],
            "open": clean_close,
            "high": [value + 1 for value in clean_close],
            "low": [value - 1 for value in clean_close],
            "close": clean_close,
            "adj_close": clean_close,
            "volume": 100,
        }
    )
    injected_dates = ["4", "8"]
    frame.loc[frame["date"].isin(injected_dates), ["open", "high", "low", "close"]] = 0

    flagged = check_non_positive_price(frame, {})
    naive_volatility = annualized_volatility(frame)
    cleaned = frame.loc[~frame["date"].isin(flagged["date"])].copy()
    cleaned_volatility = annualized_volatility(cleaned)

    assert not pd.notna(naive_volatility) or not np.isfinite(naive_volatility)
    assert np.isfinite(cleaned_volatility) and cleaned_volatility > 0
    assert sorted(flagged["date"].tolist()) == injected_dates
