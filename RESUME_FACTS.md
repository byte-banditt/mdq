# Resume facts — measured values only

- Built automated Pandas/SQL pipeline for **21 NSE equity symbols plus Nifty 50** (22 configured instruments), covering **2021-10-04 through 2026-10-01** (1,240 rows per instrument; 27,280 stored rows), with SQLite idempotent incremental loads and Linux cron entry point.
- Packaged six data-quality checks; **28 pytest tests**; checks flagged **20 issue rows** on real history in latest run: 5 error rows and 15 warning rows. The five error rows were null OHLC bars for `^NSEI`; no zero-price issue was detected in real run. The real-data impact is negligible (ratio ~1.0) because the 5 error rows are null OHLC bars on `^NSEI`, not price corruption in equities.
- Synthetic only: naive return volatility with injected zero-price ticks is **UNDEFINED (inf/NaN)**. `non_positive_price` flags injected dates `4` and `8`; after excluding those rows, measured annualized volatility is finite (**0.682280369**). Clean data feeds Single Index Model example and openpyxl Excel pack.

## Skills evidenced

Python, Pandas, NumPy, SQL, SQLite, ETL, Git, Linux/cron entry point, yfinance, pytest, openpyxl. R not included; optional milestone 7 was not built.

Coverage.py via pytest-cov: total **97.32%**. Per module: `checks.py` **100.00%**, `clean.py` **100.00%**, `cli.py` **95.24%**, `ingest.py` **95.70%**, `report.py` **95.71%**, `store.py` **100.00%**, `__init__.py` **100.00%**.
