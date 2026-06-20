"""
runner.py
=========
Parallel runner for all table reconciliations.

Usage
-----
python runner.py

Configuration is read from .env:
  CONFIG_DIR   - directory with *.json configs
  OUTPUT_DIR   - where reports are written
  MAX_WORKERS  - parallel threads (default: number of tables)

Adding a new table:
  1. Create script_configs/<newtable>.json
  2. DB expert fills in base_query + where_clause
  3. Re-run runner.py
"""

import argparse
import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

try:
    from reconciler import reconcile, load_config
except ImportError:
    print("❌  Cannot import reconciler.py — make sure it is in the same directory as runner.py")
    sys.exit(1)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("runner")


def discover_configs(config_dir: str) -> list[Path]:
    """Return sorted list of all JSON config paths in config_dir."""
    base = Path(config_dir)
    if not base.exists():
        raise FileNotFoundError(f"Config directory not found: {config_dir}")

    configs = sorted(base.glob("*.json"))
    if not configs:
        raise FileNotFoundError(f"No *.json config files found in: {config_dir}")

    return configs


def run_one(config_path: Path, output_dir: str) -> dict:
    """Thread worker: reconcile one table and return its report dict."""
    try:
        cfg   = load_config(str(config_path))
        table = cfg["table_name"]
        logger.info("▶  Starting  %s", table)
        report = reconcile(str(config_path), output_dir)
        status = "❌  ERRORS" if report.get("errors") else (
                 "⚠️  MISMATCHES" if report.get("mismatches") else "✅  CLEAN")
        logger.info("■  Finished  %s  →  %s", table, status)
        return report
    except Exception as exc:
        logger.exception("Fatal error running config %s", config_path)
        return {
            "table":  config_path.stem.upper(),
            "errors": [str(exc)],
            "mismatches": {},
        }


def main():
    parser = argparse.ArgumentParser(
        description="Parallel reconciliation runner — AlloyDB (Postgres) ↔ Oracle"
    )
    # Removed --tables argument – always run all configs
    args = parser.parse_args()

    # ── Read settings from .env ───────────────────────────────────────────────
    config_dir  = os.getenv("CONFIG_DIR", "script_configs")
    output_dir  = os.getenv("OUTPUT_DIR", "reports")
    max_workers = int(os.getenv("MAX_WORKERS", "0"))  # 0 means auto (len(configs))

    # ── Validate DB env vars ──────────────────────────────────────────────────
    required_env = ["ORACLE_USER", "ORACLE_PASSWORD", "ORACLE_DSN",
                    "PG_HOST", "PG_DATABASE", "PG_USER", "PG_PASSWORD"]
    missing_env = [v for v in required_env if not os.getenv(v)]
    if missing_env:
        print(f"❌  Missing environment variables: {missing_env}")
        print("    Set them in your .env file or environment before running.")
        sys.exit(1)

    # ── Discover all configs ─────────────────────────────────────────────────
    try:
        configs = discover_configs(config_dir)
    except (FileNotFoundError, ValueError) as exc:
        print(f"❌  {exc}")
        sys.exit(1)

    logger.info("Tables to reconcile: %s", [c.stem for c in configs])
    logger.info("Output directory   : %s", output_dir)
    workers = max_workers if max_workers > 0 else len(configs)
    logger.info("Max workers        : %s", workers)

    # ── Run in parallel ───────────────────────────────────────────────────────
    reports = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(run_one, cfg_path, output_dir): cfg_path
            for cfg_path in configs
        }
        for future in as_completed(futures):
            cfg_path = futures[future]
            try:
                report = future.result()
                reports.append(report)
            except Exception as exc:
                logger.exception("Unexpected error for %s", cfg_path)
                reports.append({"table": cfg_path.stem.upper(), "errors": [str(exc)], "mismatches": {}})


    if any(r.get("errors") for r in reports):
        sys.exit(2)


if __name__ == "__main__":
    main()