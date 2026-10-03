# Data source

## Yahoo Finance via yfinance

The only source is Yahoo Finance, accessed by the community-maintained `yfinance` Python package (`yf.download`). NSE equity symbols use `.NS`; Nifty 50 uses `^NSEI`. Download request sets `auto_adjust=False`, `actions=False`, and daily interval defaults, retaining source `Open`, `High`, `Low`, `Close`, `Adj Close`, and `Volume`. `Adj Close` is used for return outlier and analyst returns; raw OHLC supports integrity checks. The former `TATAMOTORS` symbol was changed to `TMPV` effective 2025-10-24; current config uses `TMPV.NS`. [NSE circular](https://nsearchives.nseindia.com/content/circulars/FAOP70882.pdf). Date `end` is exclusive. yfinance 1.3.0 live verification on 2026-10-03 fetched four recent `^NSEI` rows (latest returned date 2026-10-01) with a six-field MultiIndex response; this is one successful connectivity check, not a guarantee of future uptime or completeness.

The wrapper is unofficial and Yahoo Finance has no stable public API contract through yfinance. Responses can be rate-limited, revised, absent for symbols, or shaped as MultiIndex columns; the downloader normalizes the observed form and retries three times with 1s then 2s waits. The index series is the trading-session reference. Dates, corporate actions, adjusted history, and coverage can change between requests.

## Terms and permitted use

Yahoo Finance content is subject to Yahoo's current [Terms of Service](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html) and market-data provider restrictions; yfinance itself states its intended use is research/educational and points users to Yahoo terms. Those terms can limit automated collection, archiving, redistribution, and commercial use. This repository is a personal educational example. Do not publish or redistribute downloaded prices, use them in a commercial service, or assume long-term local retention is permitted without confirming applicable terms and obtaining required rights. The owner must check current terms for their jurisdiction and use before operating recurring collection. This project does not claim a data license.
