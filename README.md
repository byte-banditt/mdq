# mdq — Daily NSE Data Pipeline

Small Python/Pandas/SQLite pipeline for daily NSE prices. It ingests yfinance data, records six quality checks, excludes error rows from clean prices, and exports returns plus an issue log to Excel. The project is for personal learning and analysis; review provider terms before retaining, sharing, or using market data commercially.

## Install

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
mdq init-db
```

Python 3.10+ required. Config and thresholds live in `config.yaml`; default history begins five years before the checked-in date. SQLite DB is created at `data/mdq.sqlite`.

## Run

```sh
mdq run             # incremental, with five calendar days overlap
mdq run --full      # fetch configured history again; upserts preserve one row per key
```

Run output is written to `output/analyst_pack_YYYY-MM-DD.xlsx`; application logs go to `logs/mdq.log`. Excel contains clean adjusted-close returns, issue counts, and issue details. `RESULTS.md` is rewritten from the completed run. A source/network failure is retried three times and leaves database price tables untouched because download completes before writes.

Cron example (daily at 18:30 UTC; adjust for NSE close and your machine timezone):

```cron
30 18 * * 1-5 /absolute/path/to/mdq/scripts/run_daily.sh
```

Script activates `.venv` if present and appends cron output to `logs/cron.log`.

## Data quality behavior

Error rows (non-positive/null OHLC, inconsistent OHLC, source-batch duplicates) remain in raw storage and are excluded from clean. Warnings (missing index sessions, stale close, adjusted-return robust-z outliers) remain in clean and are logged. No repair or imputation occurs. A clean-table rebuild is deterministic from raw rows and the current full-history check run.

## Development

```sh
pytest -q --cov=mdq --cov-report=term-missing --cov-report=json
ruff check src tests
```

The tests use committed CSV/synthetic fixtures and do not access network. Synthetic zero-tick volatility demonstration is explicitly not a real-data finding. See `docs/DATA_SOURCES.md`, `docs/INTERVIEW_NOTES.md`, and `sql/queries.sql`.

## Limits

One free-data source, daily bars, SQLite single-writer workflow, no cross-source validation, no correction/imputation. Yahoo Finance data can be delayed or revised; NSE holidays are inferred from the fetched Nifty index dates and can inherit source gaps. A single index-symbol fetch gap weakens the missing-session reference.
