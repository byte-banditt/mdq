# Run results

Generated from run `c507a8dc-8bb9-4eee-b091-b9d291cb2cc2` at 2026-10-03T09:05:50.191609+00:00.

- Symbols configured: 22
- Data range: 2021-10-04 to 2026-10-01
- Rows ingested this run: 88
- Total stored rows: 27280
- Rows excluded from clean: 5
- Pipeline runtime: 6.64 seconds
- Pytest count: 15
- Statement-line coverage: checks.py 84.2%, clean.py 86.4%
  (stdlib trace + AST metric)

## Issues by check

- non_positive_price (error): 5
- return_outlier (warning): 15

## Volatility impact (real data)

- ^NSEI: raw=0.13847, clean=0.138508, ratio=0.999724

## Synthetic zero-tick demonstration

- Clean annualized volatility: 0.004739682022152733
- With injected zero-price ticks: INFINITE
- Ratio: INFINITE (synthetic only; log return at zero is infinite)
