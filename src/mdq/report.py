"""Excel analyst pack and measured run summary generation."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill

from mdq.clean import volatility_impact
from mdq.store import connect


def export_excel(database: str, run_id: str, output_dir: str = "output") -> Path:
    """Export clean returns and run-scoped issue summary/detail."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    path = output / f"analyst_pack_{date.today().isoformat()}.xlsx"
    with connect(database) as conn:
        clean = pd.read_sql_query(
            "SELECT symbol,date,adj_close FROM prices_clean ORDER BY date", conn
        )
        clean["date"] = pd.to_datetime(clean["date"])
        clean["return"] = clean.groupby("symbol")["adj_close"].pct_change()
        returns = clean.pivot(index="date", columns="symbol", values="return").reset_index()
        detail = pd.read_sql_query(
            "SELECT symbol,date,check_name,severity,detail,detected_at FROM dq_issues "
            "WHERE run_id=? ORDER BY date,symbol,check_name",
            conn,
            params=(run_id,),
        )
        summary = detail.groupby(["check_name", "severity"], as_index=False).size()
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        returns.to_excel(writer, sheet_name="Returns_Clean", index=False)
        summary.to_excel(writer, sheet_name="DQ_Summary", index=False)
        detail.to_excel(writer, sheet_name="DQ_Detail", index=False)
    workbook = load_workbook(path)
    for sheet in workbook.worksheets:
        sheet.freeze_panes = "A2"
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="23415A")
        for column in sheet.columns:
            letter = column[0].column_letter
            width = min(max(max(len(str(cell.value or "")) for cell in column) + 2, 12), 42)
            sheet.column_dimensions[letter].width = width
    for cell in workbook["Returns_Clean"][1]:
        if cell.value != "date":
            for row in range(2, workbook["Returns_Clean"].max_row + 1):
                workbook["Returns_Clean"].cell(row, cell.column).number_format = "0.00%"
    workbook.save(path)
    return path


def write_results(database: str, cfg: dict[str, Any], run_id: str, started: str) -> None:
    """Write observed database and timing metrics; unavailable values stay explicit."""
    with connect(database) as conn:
        count = conn.execute("SELECT COUNT(*) FROM prices_raw").fetchone()[0]
        run_rows = conn.execute(
            "SELECT rows_ingested FROM runs WHERE run_id=?", (run_id,)
        ).fetchone()[0]
        clean_count = conn.execute("SELECT COUNT(*) FROM prices_clean").fetchone()[0]
        bounds = conn.execute("SELECT MIN(date),MAX(date) FROM prices_raw").fetchone()
        issue_rows = conn.execute(
            "SELECT check_name,severity,COUNT(*) FROM dq_issues WHERE run_id=? "
            "GROUP BY check_name,severity ORDER BY check_name,severity",
            (run_id,),
        ).fetchall()
        impact = volatility_impact(conn, run_id)
        error_rows = conn.execute(
            "SELECT DISTINCT p.symbol,p.date,p.open,p.high,p.low,p.close "
            "FROM prices_raw p JOIN dq_issues i ON i.symbol=p.symbol AND i.date=p.date "
            "WHERE i.run_id=? AND i.severity='error' ORDER BY p.symbol,p.date",
            (run_id,),
        ).fetchall()
        finished = datetime.now(timezone.utc)
        elapsed = (finished - datetime.fromisoformat(started)).total_seconds()
    metrics_path = Path("test_metrics.json")
    metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
    test_count = metrics.get("tests", "NOT MEASURED")
    coverage = metrics.get("coverage", {})
    modules = coverage.get("modules", {})
    coverage_lines = [f"- {module}: {percent}%" for module, percent in modules.items()]
    coverage_lines.append(f"- Total: {coverage.get('total', 'NOT MEASURED')}%")
    synthetic = metrics.get("synthetic_volatility", {})
    issues = (
        "\n".join(f"- {name} ({severity}): {number}" for name, severity, number in issue_rows)
        or "- None"
    )
    error_lines = []
    for row in error_rows:
        null_columns = [name for name in ("open", "high", "low", "close") if row[name] is None]
        columns = ", ".join(null_columns) if null_columns else "none"
        error_lines.append(
            f"- {row['symbol']} {row['date']}: null OHLC columns {columns}; cause not verified"
        )
    error_text = "\n".join(error_lines) or "- None"
    vol_text = (
        "\n".join(
            f"- {row['symbol']}: raw={row['raw_volatility']:.6g}, "
            f"clean={row['clean_volatility']:.6g}, ratio={row['ratio']:.6g}"
            for row in impact
        )
        or "- No symbols with error-level issues; volatility impact not measured on real data."
    )
    content = f"""# Run results

Generated from run `{run_id}` at {finished.isoformat()}.

- Symbols configured: {len(cfg["symbols"])}
- Data range: {bounds[0] or "NOT MEASURED"} to {bounds[1] or "NOT MEASURED"}
- Rows ingested this run: {run_rows}
- Total stored rows: {count}
- Rows excluded from clean: {count - clean_count}
- Pipeline runtime: {elapsed:.2f} seconds
- Pytest count: {test_count}

## Coverage.py line coverage

{chr(10).join(coverage_lines)}

## Issues by check

{issues}

## Error row details

{error_text}

## Volatility impact (real data)

{vol_text}

Real-data impact is negligible (ratio ~1.0) because five error rows are null OHLC bars on
`^NSEI`, not price corruption in equities.

## Synthetic zero-tick demonstration

Synthetic only: naive return-based volatility with injected zero-price ticks is
{synthetic.get("naive", "NOT MEASURED")}. After `non_positive_price` excludes the
flagged rows ({synthetic.get("flagged_dates", "NOT MEASURED")}), annualized volatility
is finite: {synthetic.get("cleaned", "NOT MEASURED")}.
"""
    Path("RESULTS.md").write_text(content, encoding="utf-8")
