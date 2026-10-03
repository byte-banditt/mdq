from pathlib import Path

import pandas as pd

from mdq.ingest import upsert_prices
from mdq.store import connect, init_db


def test_fixture_upsert_is_idempotent(tmp_path):
    db = str(tmp_path / "test.sqlite")
    init_db(db)
    frame = pd.read_csv(Path(__file__).parent / "fixtures" / "prices.csv")
    with connect(db) as conn:
        assert upsert_prices(conn, frame, "2024-01-03T00:00:00Z") == 3
        assert upsert_prices(conn, frame, "2024-01-03T00:00:00Z") == 3
        before = conn.execute("SELECT * FROM prices_raw ORDER BY symbol,date").fetchall()
        assert upsert_prices(conn, frame, "2024-01-04T00:00:00Z") == 3
        after = conn.execute("SELECT * FROM prices_raw ORDER BY symbol,date").fetchall()
        assert before == after
        assert conn.execute("SELECT COUNT(*) FROM prices_raw").fetchone()[0] == 3
