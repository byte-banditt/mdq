"""Run offline tests and measure checks.py/clean.py statement-line coverage."""

import ast
import json
import math
import sys
import trace
from pathlib import Path

import pandas as pd
import pytest

from mdq.clean import annualized_volatility

ROOT = Path(__file__).resolve().parents[1]
FILES = [ROOT / "src/mdq/checks.py", ROOT / "src/mdq/clean.py"]
STATEMENTS = (
    ast.Assign,
    ast.AnnAssign,
    ast.AugAssign,
    ast.Expr,
    ast.Return,
    ast.Raise,
    ast.If,
    ast.For,
    ast.While,
    ast.Try,
    ast.With,
    ast.Assert,
    ast.FunctionDef,
)


class TestCounter:
    count = 0

    def pytest_collection_finish(self, session):
        self.count = len(session.items)


def statement_lines(path: Path) -> set[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    lines = set()
    for node in ast.walk(tree):
        if isinstance(node, STATEMENTS):
            if (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                continue
            lines.add(node.lineno)
    return lines


def main() -> None:
    counter = TestCounter()
    tracer = trace.Trace(count=True, trace=False, ignoredirs=(sys.prefix, sys.base_prefix))
    result = tracer.runfunc(pytest.main, ["-q"], plugins=[counter])
    counts = tracer.results().counts
    coverage = {}
    for path in FILES:
        lines = statement_lines(path)
        executed = {
            line
            for (filename, line), hits in counts.items()
            if Path(filename).resolve() == path and hits > 0
        }
        hit = len(lines & executed)
        coverage[path.name] = {
            "covered": hit,
            "statements": len(lines),
            "percent": round(100 * hit / len(lines), 1),
        }
    synthetic = pd.DataFrame({"date": range(12), "close": [100 + i for i in range(12)]})
    corrupted = synthetic.copy()
    corrupted.loc[[4, 8], "close"] = 0
    clean_vol = annualized_volatility(synthetic)
    raw_vol = annualized_volatility(corrupted)
    ratio = raw_vol / clean_vol
    raw_vol = raw_vol if math.isfinite(raw_vol) else "INFINITE"
    ratio = ratio if math.isfinite(ratio) else "INFINITE"
    payload = {
        "tests": counter.count,
        "coverage": coverage,
        "synthetic_volatility": {
            "clean": clean_vol,
            "with_zero_ticks": raw_vol,
            "ratio": ratio,
        },
        "pytest_exit_code": int(result),
    }
    (ROOT / "test_metrics.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    raise SystemExit(int(result))


if __name__ == "__main__":
    main()
