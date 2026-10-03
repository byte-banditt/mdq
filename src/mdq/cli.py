"""Command-line entry point."""

import argparse
import logging
from pathlib import Path

from mdq.store import init_db, load_config


def main() -> None:
    parser = argparse.ArgumentParser(prog="mdq")
    parser.add_argument("command", choices=["init-db", "run"])
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(
        filename="logs/mdq.log", level=logging.INFO, format="%(asctime)s %(message)s"
    )
    cfg = load_config(args.config)
    if args.command == "init-db":
        init_db(cfg["database"])
        print(f"Initialized {cfg['database']}")
        return
    from mdq.ingest import run_pipeline

    run_pipeline(cfg, full=args.full)


if __name__ == "__main__":
    main()
