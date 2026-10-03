"""Shared offline price fixture and temporary pipeline config."""

from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def prices_frame() -> pd.DataFrame:
    """Load small committed price rows; never contact the source."""
    return pd.read_csv(Path(__file__).parent / "fixtures" / "prices.csv")


@pytest.fixture
def pipeline_config(tmp_path: Path) -> dict:
    return {
        "database": str(tmp_path / "mdq.sqlite"),
        "start_date": "2024-01-01",
        "end_date": "2024-01-10",
        "overlap_days": 5,
        "symbols": ["AAA.NS", "BBB.NS"],
        "checks": {"stale_sessions": 5, "return_outlier_robust_z": 8.0},
    }
