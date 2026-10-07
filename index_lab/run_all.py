"""Rebuild artifacts from existing SQLite; no network calls."""

import argparse

from indexkit.data import ROOT, config, load, prices, quality
from indexkit.index_engine import benchmark, build, modification_demo


def run(fast=False, cfg=None):
    cfg = config() if cfg is None else cfg
    cfg["fast"] = fast
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "docs").mkdir(exist_ok=True)
    if fast:
        for stale in ["autocallable.csv", "autocall_probabilities.csv", "autocall_delta.png"]:
            (ROOT / "reports" / stale).unlink(missing_ok=True)
    frame, audit = load(cfg)
    cfg["source_start"] = str(frame.date.min().date())
    cfg["source_end"] = str(frame.date.max().date())
    print(audit)
    (ROOT / "docs" / "data_inventory.md").write_text(
        "# Actual mdq inventory\n```\n" + audit + "\n```\n"
    )
    quality(frame, cfg).to_csv(ROOT / "reports" / "source_dq.csv", index=False)
    if cfg.get("start"):
        frame = frame[frame.date >= cfg["start"]]
    if cfg.get("end"):
        frame = frame[frame.date <= cfg["end"]]
    panel = prices(frame, cfg)
    results = {name: build(panel, name, cfg) for name in cfg["indices"]}
    for name, result in results.items():
        for attr in ("levels", "weights", "turnover", "changes", "contributions"):
            getattr(result, attr).to_csv(
                ROOT / "reports" / f"{name}_{attr}.csv", index=attr not in ("turnover", "changes")
            )
        modification_demo(panel, name, cfg).to_csv(
            ROOT / "reports" / f"{name}_modifications.csv", index=False
        )
    bench = benchmark(panel, next(iter(results.values())).levels.index, cfg)
    bench.to_csv(ROOT / "reports" / "benchmark.csv")
    from indexkit.monitor import monitor, rebalance_report

    log = monitor(frame, panel, results, cfg)
    log.to_csv(ROOT / "reports" / "monitor_log.csv", index=False)
    log.groupby(["check_name", "severity"]).size().rename("count").to_csv(
        ROOT / "reports" / "monitor_summary.csv"
    )
    for name, result in results.items():
        rebalance_report(result, panel, cfg, log).to_csv(
            ROOT / "reports" / f"{name}_rebalance_report.csv", index=False
        )
    import pandas as pd
    from indexkit.attribution import brinson, contributors
    from indexkit.stress import betas, composition, historical, hypothetical

    sectors = pd.read_csv(ROOT / cfg["sector_inputs"]).set_index("symbol").sector.to_dict()
    for name, result in results.items():
        a, m, res = brinson(result, panel, bench, sectors)
        stocks, sector, stats = composition(result, sectors, betas(panel, bench, cfg), panel)
        outputs = {
            "attribution": a,
            "monthly": m,
            "compounding_bridge": res,
            "contributors": contributors(result),
            "composition": stocks,
            "sector_weights": sector,
            "concentration": stats,
            "historical_stress": historical(panel, stocks, cfg),
            "hypothetical_stress": hypothetical(stocks),
        }
        for label, table in outputs.items():
            table.to_csv(ROOT / "reports" / f"{name}_{label}.csv", index=False)
    from indexkit.options import artifacts

    artifacts(cfg)
    from indexkit.rates import pricing_sheet

    pricing_sheet(cfg, fast)
    from indexkit.structured import artifacts as structured_artifacts

    structured_artifacts(cfg, fast)
    from indexkit.reporting import generate

    generate(results, bench, cfg, log)
    return cfg, frame, panel, results, bench


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fast", action="store_true")
    run(parser.parse_args().fast)
