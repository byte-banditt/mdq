# Interview notes — owner should rewrite in own words

1. **Why SQLite, not Postgres?** Zero setup for a single-user batch job. Transforms stay plain SQL; a server database is a reasonable next step when concurrent writers or shared access matter.
2. **How idempotent?** `(symbol, date)` primary keys plus `ON CONFLICT DO UPDATE`; overlap re-fetches can update corrected source bars without duplicate keys.
3. **Why adjusted close for outliers, raw prices for integrity?** Splits/bonuses should not look like price shocks in adjusted-return history. Raw OHLC still must obey basic positive and range constraints.
4. **Why MAD robust z-score?** A single extreme return can inflate standard deviation and hide itself; median absolute deviation is less sensitive.
5. **Why exclude errors but retain warnings?** Impossible OHLC rows should not feed analysis. Missing bars or stale closes can have legitimate or provider-specific explanations, so they stay visible for human review.
6. **Why index calendar?** It is a simple, observable session reference. If index history misses a date, this method misses that session too.
7. **What breaks at 100x scale?** Single-process Pandas and SQLite write throughput. Partitioned storage and a scheduler/warehouse would address larger concurrent workloads.
8. **Known limits?** One unofficial source, no reconciliation, source revisions/coverage gaps, and no repair or imputation.
