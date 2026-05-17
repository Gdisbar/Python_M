"""
runner.py
=========
Parallel runner for all table reconciliations.

Usage
-----
# Run all tables defined in CONFIG_DIR (from .env, default script_configs/)
python runner.py

# Run specific tables only
python runner.py --tables charge discount

Configuration is read from .env:
  CONFIG_DIR   - directory with <table>.json configs
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


def discover_configs(config_dir: str, table_filter: list[str] | None = None) -> list[Path]:
    """Return sorted list of config JSON paths, optionally filtered by table name."""
    base = Path(config_dir)
    if not base.exists():
        raise FileNotFoundError(f"Config directory not found: {config_dir}")

    configs = sorted(base.glob("*.json"))
    if not configs:
        raise FileNotFoundError(f"No *.json config files found in: {config_dir}")

    if table_filter:
        wanted = {t.lower() for t in table_filter}
        configs = [c for c in configs if c.stem.lower() in wanted]
        if not configs:
            raise ValueError(
                f"None of the requested tables {table_filter} found in {config_dir}.\n"
                f"Available: {[c.stem for c in sorted(base.glob('*.json'))]}"
            )

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


def write_summary(reports: list[dict], output_dir: str) -> Path:
    """Write a consolidated JSON + print a text summary to stdout."""
    summary_dir = Path(output_dir) / "json_reports"
    summary_dir.mkdir(parents=True, exist_ok=True)

    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = summary_dir / f"summary_{ts}.json"

    summary = {
        "run_at":  datetime.now().isoformat(),
        "tables":  [],
        "overall": {
            "total_tables":      len(reports),
            "clean":             0,
            "with_mismatches":   0,
            "with_errors":       0,
        },
    }

    print("\n" + "="*80)
    print("  CONSOLIDATED RECONCILIATION SUMMARY")
    print("="*80)
    print(f"  {'Table':<30} {'Oracle':>8} {'Postgres':>10} {'Groups':>8} {'Mismatches':>12} {'Status'}")
    print("-"*80)

    for r in sorted(reports, key=lambda x: x.get("table", "")):
        table       = r.get("table", "?")
        ora_cnt     = r.get("oracle_row_count",   "?")
        pg_cnt      = r.get("postgres_row_count",  "?")
        grp_cnt     = r.get("common_group_keys",   "?")
        mismatch_cnt = len(r.get("mismatches", {}))
        has_errors   = bool(r.get("errors"))

        if has_errors:
            status = "❌ ERROR"
            summary["overall"]["with_errors"] += 1
        elif mismatch_cnt:
            status = f"⚠️  {mismatch_cnt} groups"
            summary["overall"]["with_mismatches"] += 1
        else:
            status = "✅ CLEAN"
            summary["overall"]["clean"] += 1

        print(f"  {table:<30} {str(ora_cnt):>8} {str(pg_cnt):>10} {str(grp_cnt):>8} {str(mismatch_cnt):>12}   {status}")

        summary["tables"].append({
            "table":              table,
            "oracle_row_count":   ora_cnt,
            "postgres_row_count": pg_cnt,
            "common_group_keys":  grp_cnt,
            "mismatch_groups":    mismatch_cnt,
            "missing_in_oracle":  r.get("missing_in_oracle",   []),
            "missing_in_postgres":r.get("missing_in_postgres", []),
            "errors":             r.get("errors", []),
            "status":             status,
            "txt_report":         r.get("_txt_path"),
            "json_report":        r.get("_json_path"),
        })

    print("-"*80)
    ov = summary["overall"]
    print(f"  Total: {ov['total_tables']}  |  ✅ Clean: {ov['clean']}  "
          f"|  ⚠️  Mismatches: {ov['with_mismatches']}  "
          f"|  ❌ Errors: {ov['with_errors']}")
    print(f"\n  📊 Summary JSON → {path}")
    print("="*80 + "\n")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str, ensure_ascii=False)

    return path


def main():
    parser = argparse.ArgumentParser(
        description="Parallel reconciliation runner — AlloyDB (Postgres) ↔ Oracle"
    )
    parser.add_argument(
        "--tables", nargs="+", metavar="TABLE",
        help="Run only these tables (by config file stem, e.g. charge discount). "
             "Omit to run all tables in CONFIG_DIR.",
    )
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

    # ── Discover configs ──────────────────────────────────────────────────────
    try:
        configs = discover_configs(config_dir, args.tables)
    except (FileNotFoundError, ValueError) as exc:
        print(f"❌  {exc}")
        sys.exit(1)

    logger.info("Tables to reconcile: %s", [c.stem for c in configs])
    logger.info("Output directory   : %s", output_dir)
    workers = max_workers if max_workers > 0 else len(configs)
    logger.info("Max workers        : %s", workers)

    # ── Run in parallel ────────────────────────────────────────────────────────
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

    # ── Summary ────────────────────────────────────────────────────────────────
    write_summary(reports, output_dir)

    if any(r.get("errors") for r in reports):
        sys.exit(2)


if __name__ == "__main__":
    main()