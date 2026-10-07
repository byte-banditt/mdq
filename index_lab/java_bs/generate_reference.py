"""Generate five fixed input cases; expected quotes always computed by Python."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from indexkit.options import vanilla


def generate(path):
    cases = [
        (100, 100, 1, 0.05, 0.2, 0.01, "call"),
        (100, 110, 0.5, 0.04, 0.3, 0, "put"),
        (125, 100, 2, 0.02, 0.15, 0.02, "call"),
        (80, 100, 0.1, 0.03, 0.4, 0.01, "put"),
        (1000, 950, 0.75, 0.06, 0.25, 0.015, "call"),
    ]
    rows = []
    for s, k, t, r, v, q, kind in cases:
        result = vanilla(s, k, t, r, v, q, kind)
        rows.append(
            dict(
                spot=s,
                strike=k,
                expiry=t,
                rate=r,
                vol=v,
                q=q,
                kind=kind,
                price=float(result["price"]),
                delta=float(result["delta"]),
            )
        )
    pd.DataFrame(rows).to_csv(path, index=False)


if __name__ == "__main__":
    generate(Path(__file__).with_name("python_reference.csv"))
