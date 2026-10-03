"""Offline integration tests for pipeline and CLI orchestration."""

import sys
from pathlib import Path

import pytest
import yaml

from mdq import cli, ingest
from mdq.ingest import run_pipeline, upsert_prices
from mdq.store import connect, init_db


def test_pipeline_twice_is_idempotent_and_records_success(
    tmp_path, monkeypatch, prices_frame, pipeline_config
):
    monkeypatch.chdir(tmp_path)
    init_db(pipeline_config["database"])
    monkeypatch.setattr(ingest, "download_prices", lambda *args: prices_frame.copy())

    run_pipeline(pipeline_config, full=True)
    with connect(pipeline_config["database"]) as conn:
        first = conn.execute("SELECT * FROM prices_raw ORDER BY symbol,date").fetchall()
    run_pipeline(pipeline_config, full=True)

    with connect(pipeline_config["database"]) as conn:
        second = conn.execute("SELECT * FROM prices_raw ORDER BY symbol,date").fetchall()
        count = conn.execute("SELECT COUNT(*) FROM prices_raw").fetchone()[0]
        successes = conn.execute("SELECT COUNT(*) FROM runs WHERE status='success'").fetchone()[0]
    assert count == len(prices_frame)
    assert second == first
    assert successes == 2


def test_failed_download_marks_run_failed_and_leaves_price_tables_unchanged(
    tmp_path, monkeypatch, prices_frame, pipeline_config
):
    monkeypatch.chdir(tmp_path)
    init_db(pipeline_config["database"])
    with connect(pipeline_config["database"]) as conn:
        upsert_prices(conn, prices_frame, "2024-01-03T00:00:00Z")
        conn.execute(
            "INSERT INTO prices_clean SELECT symbol,date,open,high,low,close,adj_close,volume "
            "FROM prices_raw"
        )
        before_raw = conn.execute("SELECT * FROM prices_raw ORDER BY symbol,date").fetchall()
        before_clean = conn.execute("SELECT * FROM prices_clean ORDER BY symbol,date").fetchall()

    def fail_download(*args):
        raise RuntimeError("offline test failure")

    monkeypatch.setattr(ingest, "download_prices", fail_download)
    with pytest.raises(RuntimeError, match="offline test failure"):
        run_pipeline(pipeline_config)

    with connect(pipeline_config["database"]) as conn:
        after_raw = conn.execute("SELECT * FROM prices_raw ORDER BY symbol,date").fetchall()
        after_clean = conn.execute("SELECT * FROM prices_clean ORDER BY symbol,date").fetchall()
        failed = conn.execute("SELECT COUNT(*) FROM runs WHERE status='failed'").fetchone()[0]
    assert after_raw == before_raw
    assert after_clean == before_clean
    assert failed == 1


def test_cli_init_db_and_run_use_temp_config_and_mocked_download(
    tmp_path, monkeypatch, prices_frame, pipeline_config
):
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(pipeline_config), encoding="utf-8")
    monkeypatch.setattr(ingest, "download_prices", lambda *args: prices_frame.copy())

    monkeypatch.setattr(sys, "argv", ["mdq", "init-db", "--config", str(config_path)])
    cli.main()
    assert Path(pipeline_config["database"]).exists()

    monkeypatch.setattr(sys, "argv", ["mdq", "run", "--config", str(config_path)])
    cli.main()
    with connect(pipeline_config["database"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM prices_raw").fetchone()[0] == len(prices_frame)
        assert conn.execute("SELECT status FROM runs").fetchone()[0] == "success"
