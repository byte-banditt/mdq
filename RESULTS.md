# Run results

Generated from run `8b26c935-4c33-4003-8245-c7b7261fc6fd` at 2026-10-03T09:28:57.196021+00:00.

- Symbols configured: 22
- Data range: 2021-10-04 to 2026-10-01
- Rows ingested this run: 88
- Total stored rows: 27280
- Rows excluded from clean: 5
- Pipeline runtime: 5.69 seconds
- Pytest count: 15
- Statement-line coverage: checks.py 68.4%, clean.py 86.4%
  (stdlib trace + AST metric)

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
