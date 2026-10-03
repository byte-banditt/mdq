import pandas as pd
import pytest

from mdq.checks import (
    check_duplicate_rows,
    check_missing_sessions,
    check_non_positive_price,
    check_ohlc_inconsistent,
    check_return_outlier,
    check_stale_price,
)

CFG = {"checks": {"stale_sessions": 2, "return_outlier_robust_z": 3}}
BASE = {
    "symbol": "A.NS",
    "open": 10.0,
    "high": 11.0,
    "low": 9.0,
    "close": 10.0,
    "adj_close": 10.0,
    "volume": 10.0,
}


def data(rows):
    return pd.DataFrame(rows)


@pytest.mark.parametrize(
    "fn, rows, expected",
    [
        (check_non_positive_price, [{**BASE, "date": "1", "open": 0}], 1),
        (check_non_positive_price, [{**BASE, "date": "1", "open": None}], 1),
        (check_non_positive_price, [{**BASE, "date": "1"}], 0),
        (check_ohlc_inconsistent, [{**BASE, "date": "1", "close": 12}], 1),
        (check_ohlc_inconsistent, [{**BASE, "date": "1", "close": 10}], 0),
        (check_ohlc_inconsistent, [{**BASE, "date": "1", "low": 10}], 0),
        (check_duplicate_rows, [{**BASE, "date": "1"}, {**BASE, "date": "1"}], 1),
        (check_duplicate_rows, [{**BASE, "date": "1"}], 0),
        (check_duplicate_rows, [{**BASE, "date": "1"}, {**BASE, "date": "2"}], 0),
    ],
)
def test_error_checks(fn, rows, expected):
    assert len(fn(data(rows), CFG)) == expected


def test_missing_sessions_absent_present_and_index_only():
    frame = data(
        [
            {**BASE, "symbol": "^NSEI", "date": "1"},
            {**BASE, "symbol": "^NSEI", "date": "2"},
            {**BASE, "symbol": "A.NS", "date": "1"},
        ]
    )
    result = check_missing_sessions(frame, CFG)
    assert result[["symbol", "date"]].values.tolist() == [["A.NS", "2"]]
    assert len(check_missing_sessions(frame.iloc[[0, 2]], CFG)) == 0
    assert len(check_missing_sessions(frame.iloc[[0]], CFG)) == 0
    configured = {"symbols": ["^NSEI", "A.NS", "B.NS"]}
    assert len(check_missing_sessions(frame, configured)) == 3


def test_stale_normal_threshold_and_zero_volume_edge():
    rows = [{**BASE, "date": str(i), "volume": 10} for i in range(3)]
    assert len(check_stale_price(data(rows), CFG)) == 2
    rows[1]["close"] = 11
    assert len(check_stale_price(data(rows), CFG)) == 0
    rows[1]["close"] = 10
    rows[2]["volume"] = 0
    assert len(check_stale_price(data(rows), CFG)) == 1


def test_return_outlier_and_flat_edge():
    closes = [10, 10.1, 10.0, 10.2, 10.1, 30]
    frame = data([{**BASE, "date": str(i), "adj_close": value} for i, value in enumerate(closes)])
    assert "5" in check_return_outlier(frame, CFG).date.tolist()
    assert check_return_outlier(data([{**BASE, "date": str(i)} for i in range(4)]), CFG).empty
    assert check_return_outlier(
        data([{**BASE, "date": str(i), "adj_close": 10} for i in range(4)]), CFG
    ).empty
