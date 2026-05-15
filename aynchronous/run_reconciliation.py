#!/usr/bin/env python3
"""
Multi-Threaded Reconciliation Runner
Automatically discovers and runs all .json config files from configs/ folder
"""

import json
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys

from reconcile_engine import reconcile_single_table


def main():
    # Create timestamped output directory
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("reports") / run_timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 90)
    print("🚀 ORACLE ↔ ALLOYDB RECONCILIATION ENGINE")
    print(f"Started At : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Output Dir : reports/{run_timestamp}/")
    print("=" * 90)

    # Discover all config files
    config_dir = Path("configs")
    if not config_dir.exists():
        print("❌ Error: 'configs/' directory not found!")
        sys.exit(1)

    config_files = list(config_dir.glob("*.json"))

    if not config_files:
        print("❌ No configuration files found in configs/ folder!")
        print("   Please place your table config files (e.g. salestran.json) inside configs/")
        sys.exit(1)

    print(f"Found {len(config_files)} configuration file(s):\n")
    for cf in config_files:
        print(f"   • {cf.name}")

    print(f"\nRunning reconciliation with {min(6, len(config_files))} threads...\n")

    # Run in parallel
    max_workers = min(6, len(config_files))   # You can increase this if needed

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_config = {
            executor.submit(reconcile_single_table, config_file.name, output_dir): config_file.name
            for config_file in config_files
        }

        completed = 0
        for future in as_completed(future_to_config):
            config_file = future_to_config[future]
            try:
                future.result()
                completed += 1
            except Exception as exc:
                print(f"❌ Failed {config_file}: {exc}")

    # Final Summary
    print("\n" + "=" * 90)
    print("✅ ALL RECONCILIATIONS FINISHED!")
    print(f"Total Tables Processed : {len(config_files)}")
    print(f"Successful             : {completed}")
    print(f"Failed                 : {len(config_files) - completed}")
    print(f"Reports Saved in       : reports/{run_timestamp}/")
    print("=" * 90)


if __name__ == "__main__":
    main()