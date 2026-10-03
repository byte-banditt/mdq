import pandas as pd

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


def test_synthetic_zero_ticks_inflate_volatility():
    """Synthetic demonstration only; does not claim real market-data prevalence."""
    clean = pd.DataFrame({"date": range(12), "close": [100 + i for i in range(12)]})
    corrupted = clean.copy()
    corrupted.loc[[4, 8], "close"] = 0
    raw_vol = annualized_volatility(corrupted)
    clean_vol = annualized_volatility(clean)
    assert raw_vol > clean_vol * 5
