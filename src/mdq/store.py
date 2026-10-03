"""SQLite storage and configuration helpers."""

import sqlite3
from pathlib import Path
from typing import Any

import yaml


def load_config(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def connect(database: str) -> sqlite3.Connection:
    Path(database).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(database: str) -> None:
    schema = Path(__file__).resolve().parents[2] / "sql" / "schema.sql"
    with connect(database) as conn:
        conn.executescript(schema.read_text(encoding="utf-8"))
