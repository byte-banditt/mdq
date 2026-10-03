# Run results

Generated from run `5fe09c42-ef05-4cbd-9756-846dec4c4612` at 2026-10-03T09:35:05.274602+00:00.

- Symbols configured: 22
- Data range: 2021-10-04 to 2026-10-01
- Rows ingested this run: 88
- Total stored rows: 27280
- Rows excluded from clean: 5
- Pipeline runtime: 6.67 seconds
- Pytest count: 17

## Coverage.py line coverage

- src/mdq/__init__.py: 100.0%
- src/mdq/checks.py: 85.9375%
- src/mdq/clean.py: 100.0%
- src/mdq/cli.py: 0.0%
- src/mdq/ingest.py: 22.580645161290324%
- src/mdq/report.py: 0.0%
- src/mdq/store.py: 87.5%
- Total: 40.0%

## Issues by check

- non_positive_price (error): 5
- return_outlier (warning): 15

## Error row details

- ^NSEI 2026-01-15: null OHLC columns open, high, low, close; cause not verified
- ^NSEI 2026-05-01: null OHLC columns open, high, low, close; cause not verified
- ^NSEI 2026-05-28: null OHLC columns open, high, low, close; cause not verified
- ^NSEI 2026-06-26: null OHLC columns open, high, low, close; cause not verified
- ^NSEI 2026-09-14: null OHLC columns open, high, low, close; cause not verified

## Volatility impact (real data)

- ^NSEI: raw=0.13847, clean=0.138508, ratio=0.999724

Real-data impact is negligible (ratio ~1.0) because five error rows are null OHLC bars on
`^NSEI`, not price corruption in equities.

## Synthetic zero-tick demonstration

Synthetic only: naive return-based volatility with injected zero-price ticks is
UNDEFINED (inf/NaN). After `non_positive_price` excludes the
flagged rows (['4', '8']), annualized volatility
is finite: 0.6822803693562768.
