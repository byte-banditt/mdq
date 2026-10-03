# DRAFT — owner must rewrite in own words and be able to defend every point.

1. **Why SQLite, not Postgres?** Zero setup for a single-user batch job. Transforms stay plain SQL; a server database is a reasonable next step when concurrent writers or shared access matter.
2. **How idempotent?** `(symbol, date)` primary keys plus `ON CONFLICT DO UPDATE`; overlap re-fetches can update corrected source bars without duplicate keys.
3. **Why adjusted close for outliers, raw prices for integrity?** Splits/bonuses should not look like price shocks in adjusted-return history. Raw OHLC still must obey basic positive and range constraints.
4. **Why MAD robust z-score?** A single extreme return can inflate standard deviation and hide itself; median absolute deviation is less sensitive.
5. **Why exclude errors but retain warnings?** Impossible OHLC rows should not feed analysis. Missing bars or stale closes can have legitimate or provider-specific explanations, so they stay visible for human review.
6. **Why index calendar?** It is a simple, observable session reference. If index history misses a date, this method misses that session too.
7. **What breaks at 100x scale?** Single-process Pandas and SQLite write throughput. Partitioned storage and a scheduler/warehouse would address larger concurrent workloads.
8. **Known limits?** One unofficial source, no reconciliation, source revisions/coverage gaps, and no repair or imputation.
9. **Why is there no volatility-impact ratio?** The synthetic zero-price example has undefined naive log-return volatility (`log(0)`). The real-data calculation still reports a ratio near 1.0; that impact is negligible and comes from null Nifty OHLC rows.
10. **What were the 5 real error rows?** `^NSEI` rows on 2026-01-15, 2026-05-01, 2026-05-28, 2026-06-26, and 2026-09-14; open, high, low, and close were null. Cause not verified.
11. **How is coverage measured?** `pytest-cov` runs `coverage.py` line coverage. Latest run: 17 tests, 40% total; module percentages are in `RESULTS.md`.
12. **What does `missing_sessions` treat as a trading day?** Any date with a row for `^NSEI` in `prices_raw`, even if OHLC is null.
