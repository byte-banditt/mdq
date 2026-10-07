"""Explain stored beginning weights, returns, costs and flags."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from indexkit.data import ROOT


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--index", required=True)
    p.add_argument("--date", required=True)
    a = p.parse_args()
    day = pd.Timestamp(a.date)
    weights = pd.read_csv(
        ROOT / "reports" / f"{a.index}_weights.csv", index_col=0, parse_dates=True
    )
    contrib = pd.read_csv(
        ROOT / "reports" / f"{a.index}_contributions.csv", index_col=0, parse_dates=True
    )
    levels = pd.read_csv(ROOT / "reports" / f"{a.index}_levels.csv", index_col=0, parse_dates=True)
    if day not in weights.index:
        raise SystemExit("No calculated holdings on this date")
    print(pd.DataFrame({"weight": weights.loc[day], "contribution": contrib.loc[day]}).to_string())
    print(levels.loc[day].to_string())
    flags = pd.read_csv(ROOT / "reports" / "monitor_log.csv", parse_dates=["date"])
    print(flags[flags.date == day].to_string(index=False))


if __name__ == "__main__":
    main()
