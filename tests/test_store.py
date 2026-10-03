"""Connection context lifetime and transaction tests."""

import sqlite3

import pytest

from mdq.store import connect


def test_connect_commits_rolls_back_and_closes(tmp_path):
    db = str(tmp_path / "transactions.sqlite")
    with connect(db) as conn:
        conn.execute("CREATE TABLE sample(value INTEGER)")
        conn.execute("INSERT INTO sample VALUES(1)")
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        conn.execute("SELECT 1")

    with pytest.raises(RuntimeError, match="abort transaction"):
        with connect(db) as conn:
            conn.execute("INSERT INTO sample VALUES(2)")
            raise RuntimeError("abort transaction")

    with connect(db) as conn:
        assert conn.execute("SELECT value FROM sample").fetchone()["value"] == 1
