CREATE TABLE IF NOT EXISTS prices_raw (
 symbol TEXT NOT NULL, date TEXT NOT NULL, open REAL, high REAL, low REAL,
 close REAL, adj_close REAL, volume REAL, ingested_at TEXT NOT NULL,
 PRIMARY KEY(symbol, date)
);
CREATE TABLE IF NOT EXISTS prices_clean (
 symbol TEXT NOT NULL, date TEXT NOT NULL, open REAL, high REAL, low REAL,
 close REAL, adj_close REAL, volume REAL, PRIMARY KEY(symbol, date)
);
CREATE TABLE IF NOT EXISTS dq_issues (
 id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, symbol TEXT NOT NULL,
 date TEXT NOT NULL, check_name TEXT NOT NULL, severity TEXT NOT NULL,
 detail TEXT NOT NULL, detected_at TEXT NOT NULL,
 UNIQUE(run_id, symbol, date, check_name)
);
CREATE TABLE IF NOT EXISTS runs (
 run_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT,
 status TEXT NOT NULL, rows_ingested INTEGER NOT NULL DEFAULT 0,
 issues_found INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_raw_symbol_date ON prices_raw(symbol, date);
CREATE INDEX IF NOT EXISTS idx_issues_run ON dq_issues(run_id);
