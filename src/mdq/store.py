"""SQLite storage and configuration helpers."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import yaml


def load_config(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as stream:
        return yaml.safe_load(stream)


@contextmanager
def connect(database: str) -> Iterator[sqlite3.Connection]:
    Path(database).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(database: str) -> None:
    schema = Path(__file__).with_name("schema.sql")
    with connect(database) as conn:
        conn.executescript(schema.read_text(encoding="utf-8"))
