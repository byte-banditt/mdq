# Resume facts — measured values only

- Built automated Pandas/SQL pipeline for **21 NSE equity symbols plus Nifty 50** (22 configured instruments), covering **2021-10-04 through 2026-10-01** (1,240 rows per instrument; 27,280 stored rows), with SQLite idempotent incremental loads and Linux cron entry point.
- Packaged six data-quality checks; **15 pytest tests**; checks flagged **20 issue rows** on real history in latest run: 5 error rows and 15 warning rows. The five error rows were null OHLC bars for `^NSEI`; no zero-price issue was detected in real run.
- Synthetic zero-tick test: clean-series annualized volatility **0.004739682**; injected zero prices make log-return volatility **infinite** (`log(0)`), so ratio is `∞×` and not a finite ratio. This is synthetic, not a real-data finding. Clean data feeds Single Index Model example and openpyxl Excel pack.

## Skills evidenced

Python, Pandas, NumPy, SQL, SQLite, ETL, Git, Linux/cron entry point, yfinance, pytest, openpyxl. R not included; optional milestone 7 was not built.

Coverage metric is stdlib `trace` execution intersected with AST statement-start lines: `checks.py` **84.2%**, `clean.py` **86.4%**. It is a lightweight project metric, not `coverage.py` branch coverage.
