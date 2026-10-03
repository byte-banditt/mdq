-- Latest available date for each symbol.
SELECT symbol, MAX(date) AS latest_date FROM prices_raw GROUP BY symbol ORDER BY symbol;

-- Issue counts by check and severity for most recent run.
SELECT check_name, severity, COUNT(*) AS issue_count FROM dq_issues
WHERE run_id = (SELECT run_id FROM runs ORDER BY started_at DESC LIMIT 1)
GROUP BY check_name, severity ORDER BY issue_count DESC;

-- Rolling 20-session close volatility by symbol (SQLite window functions).
WITH returns AS (
  SELECT symbol, date, log(close / LAG(close) OVER (PARTITION BY symbol ORDER BY date)) AS log_return
  FROM prices_clean WHERE close > 0
)
SELECT symbol, date, sqrt(AVG(log_return * log_return) OVER (
  PARTITION BY symbol ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
)) AS rolling_rms_return
FROM returns;

-- Largest absolute one-day close moves per symbol.
WITH moves AS (
  SELECT symbol, date, close / LAG(close) OVER (PARTITION BY symbol ORDER BY date) - 1 AS daily_return
  FROM prices_clean WHERE close > 0
)
SELECT symbol, date, daily_return FROM moves WHERE daily_return IS NOT NULL
ORDER BY ABS(daily_return) DESC LIMIT 20;

-- Symbols with missing index-calendar sessions.
SELECT symbol, COUNT(*) AS missing_sessions FROM dq_issues
WHERE check_name = 'missing_sessions' GROUP BY symbol ORDER BY missing_sessions DESC;
