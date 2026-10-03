# Run results

Generated from run `958a1a96-5b0c-4945-adac-b8795b6efc34` at 2026-10-03T09:27:21.136054+00:00.

- Symbols configured: 22
- Data range: 2021-10-04 to 2026-10-01
- Rows ingested this run: 88
- Total stored rows: 27280
- Rows excluded from clean: 5
- Pipeline runtime: 6.72 seconds
- Pytest count: 15
- Statement-line coverage: checks.py 68.4%, clean.py 86.4%
  (stdlib trace + AST metric)

## Issues by check

- non_positive_price (error): 5
- return_outlier (warning): 15

## Volatility impact (real data)

- ^NSEI: raw=0.13847, clean=0.138508, ratio=0.999724

## Synthetic zero-tick demonstration

Synthetic only: naive return-based volatility with injected zero-price ticks is
UNDEFINED (inf/NaN). After `non_positive_price` excludes the
flagged rows (['4', '8']), annualized volatility
is finite: 0.6822803693562768.
