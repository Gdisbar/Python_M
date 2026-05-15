#!/usr/bin/env python3
"""
Reconciliation Engine - Individual Config File per Table
"""

import json
from datetime import datetime
from decimal import Decimal
import os
import unicodedata
from pathlib import Path
import threading
from contextlib import redirect_stdout

import oracledb
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# Thread-safe reentrant lock
print_lock = threading.RLock()


def normalize_value(val):
    if isinstance(val, str):
        return unicodedata.normalize('NFKC', val.strip())
    return val


def values_equal(a, b, alloy_type=None, onprem_type=None):
    """Compare values with data type awareness"""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return str(a).strip() == "" and str(b).strip() == ""

    a = normalize_value(a)
    b = normalize_value(b)

    try:
        # Numeric fields
        if any(t and ('numeric' in str(t).lower() or t in ('int8', 'int4', 'NUMBER', 'decimal'))
               for t in [alloy_type, onprem_type]):
            da = Decimal(str(a))
            db = Decimal(str(b))
            return abs(da - db) <= Decimal('0.01')

        # Date / Timestamp fields
        elif any(t and ('time' in str(t).lower() or t == 'DATE') for t in [alloy_type, onprem_type]):
            if isinstance(a, datetime) and isinstance(b, datetime):
                return a.replace(microsecond=0) == b.replace(microsecond=0)
            return str(a)[:19] == str(b)[:19]

        # String fields
        else:
            return str(a).strip().lower() == str(b).strip().lower()
    except Exception:
        return str(a).strip().lower() == str(b).strip().lower()


def get_oracle_conn():
    return oracledb.connect(
        user=os.getenv("ORACLE_USER"),
        password=os.getenv("ORACLE_PASSWORD"),
        dsn=os.getenv("ORACLE_DSN")
    )


def get_postgres_conn():
    return psycopg2.connect(
        host=os.getenv("PG_HOST"),
        port=os.getenv("PG_PORT", "5432"),
        dbname=os.getenv("PG_DATABASE"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD")
    )


# ========================== DATA FETCHING ==========================
def fetch_oracle_data(conn, config: dict, source_numbers: list):
    """Fetch data from Oracle"""
    cur = conn.cursor()
    placeholders = ','.join([f"'{sn}'" for sn in source_numbers])
    sql = f"""
        SELECT * 
        FROM {config['oracle_schema']}.{config['oracle_table']} 
        WHERE SOURCENUMBER IN ({placeholders})
    """
    cur.execute(sql)
    col_names = [desc[0].upper() for desc in cur.description]
    rows = cur.fetchall()
    cur.close()
    return col_names, rows


def fetch_postgres_data(conn, config: dict, source_numbers: list):
    """Fetch data from AlloyDB (Postgres)"""
    cur = conn.cursor()
    placeholders = ','.join([f"'{sn}'" for sn in source_numbers])
    sql = f"""
        SELECT * 
        FROM {config['alloydb_schema']}.{config['alloydb_table']} 
        WHERE sourcenumber IN ({placeholders})
    """
    cur.execute(sql)
    col_names = [desc[0].upper() for desc in cur.description]
    rows = cur.fetchall()
    cur.close()
    return col_names, rows


# ========================== MAIN RECONCILIATION FUNCTION ==========================
def reconcile_single_table(config_file: str, output_dir: Path):
    """Reconcile one table using its dedicated config file"""
    config_path = Path("configs") / config_file
    
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, encoding='utf-8') as f:
        config = json.load(f)

    table_key = config.get("table_key", Path(config_file).stem)

    with print_lock:
        print(f"[{threading.current_thread().name}] Starting reconciliation: {table_key} ({config_file})")

    SOURCE_NUMBERS = [s.strip() for s in os.getenv("SOURCE_NUMBERS", "").split(",") if s.strip()]

    # Output files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{config['alloydb_table']}_{config['oracle_table']}"
    
    txt_log = output_dir / f"{base_name}_{timestamp}.txt"
    json_report = output_dir / f"{base_name}_{timestamp}.json"

    with open(txt_log, "w", encoding="utf-8") as f, redirect_stdout(f):
        print(f"RECONCILIATION REPORT: {table_key.upper()}")
        print(f"Config File : {config_file}")
        print(f"AlloyDB     : {config['alloydb_schema']}.{config['alloydb_table']}")
        print(f"Oracle      : {config['oracle_schema']}.{config['oracle_table']}")
        print(f"Run Time    : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Source Numbers: {SOURCE_NUMBERS}")
        print("=" * 140)

        ora_conn = get_oracle_conn()
        pg_conn = get_postgres_conn()

        try:
            # Fetch Data
            ora_cols, ora_rows = fetch_oracle_data(ora_conn, config, SOURCE_NUMBERS)
            pg_cols, pg_rows = fetch_postgres_data(pg_conn, config, SOURCE_NUMBERS)

            # Group by SOURCENUMBER
            oracle_data = {}
            for row in ora_rows:
                sn = str(row[ora_cols.index("SOURCENUMBER")])
                oracle_data.setdefault(sn, []).append(dict(zip(ora_cols, row)))

            postgres_data = {}
            for row in pg_rows:
                sn = str(row[pg_cols.index("SOURCENUMBER")])
                postgres_data.setdefault(sn, []).append(dict(zip(pg_cols, row)))

            # Initialize Report
            report = {
                "table_key": table_key,
                "config_file": config_file,
                "alloydb_table": f"{config['alloydb_schema']}.{config['alloydb_table']}",
                "oracle_table": f"{config['oracle_schema']}.{config['oracle_table']}",
                "reconciled_on": datetime.now().isoformat(),
                "source_numbers": SOURCE_NUMBERS,
                "oracle_row_count": sum(len(v) for v in oracle_data.values()),
                "postgres_row_count": sum(len(v) for v in postgres_data.values()),
                "missing_in_oracle": list(set(postgres_data.keys()) - set(oracle_data.keys())),
                "missing_in_postgres": list(set(oracle_data.keys()) - set(postgres_data.keys())),
                "mismatches_by_sourcenumber": {},
                "renamed_columns_comparison": {}
            }

            common_sns = set(oracle_data.keys()) & set(postgres_data.keys())

            for sn in sorted(common_sns):
                o_row = oracle_data[sn][0]
                p_row = postgres_data[sn][0]

                mismatches = {}
                renamed_comparisons = {}

                for pg_col, mapping in config["column_mapping"].items():
                    if pg_col.upper() == "SOURCENUMBER":
                        continue

                    ora_col = mapping[0]
                    alloy_type = mapping[1]
                    onprem_type = mapping[2] if len(mapping) > 2 else None

                    pg_val = p_row.get(pg_col.upper())
                    ora_val = o_row.get(ora_col) if ora_col else None

                    is_renamed = (pg_col.upper() != (ora_col or "").upper())

                    if not values_equal(pg_val, ora_val, alloy_type, onprem_type):
                        mismatches[pg_col] = {
                            "alloydb_value": pg_val,
                            "alloydb_type": alloy_type,
                            "onprem_value": ora_val,
                            "onprem_column": ora_col,
                            "onprem_type": onprem_type
                        }
                    elif is_renamed:
                        renamed_comparisons[pg_col] = {
                            "alloydb_value": pg_val,
                            "onprem_value": ora_val,
                            "onprem_column": ora_col
                        }

                # Print Mismatches
                if mismatches:
                    report["mismatches_by_sourcenumber"][sn] = {
                        "mismatch_count": len(mismatches),
                        "columns": mismatches
                    }
                    print(f"\n🔴 MISMATCH → SOURCENUMBER: {sn} ({len(mismatches)} differences)")
                    for col, diff in mismatches.items():
                        print(f"   • {col:40} | AlloyDB : {diff['alloydb_value']}")
                        print(f"   {'':40} | On-Prem : {diff['onprem_value']}  ({diff['onprem_column']}) ({diff['onprem_type']})")

                # Print Renamed Columns (even if matched)
                if renamed_comparisons:
                    report["renamed_columns_comparison"][sn] = renamed_comparisons
                    print(f"\n🔄 Renamed Columns (Values Matched) → SOURCENUMBER: {sn}")
                    for col, info in renamed_comparisons.items():
                        print(f"   • {col:40} → {info['onprem_column']:25} | Value: {info['alloydb_value']}")

            # Final Summary
            print("\n" + "="*140)
            print("FINAL SUMMARY")
            print("="*140)
            print(f"Total SOURCENUMBERs Compared : {len(common_sns)}")
            print(f"SOURCENUMBERs with Mismatches: {len(report['mismatches_by_sourcenumber'])}")
            print(f"Missing in Oracle            : {len(report['missing_in_oracle'])}")
            print(f"Missing in On-Prem           : {len(report['missing_in_postgres'])}")

            # Save JSON Report
            with open(json_report, "w", encoding='utf-8') as jf:
                json.dump(report, jf, indent=2, default=str, ensure_ascii=False)

            print(f"\n✅ Reconciliation Completed for {table_key}")
            print(f"📝 Text Log : {txt_log.name}")
            print(f"📊 JSON     : {json_report.name}")

        finally:
            ora_conn.close()
            pg_conn.close()

    with print_lock:
        print(f"✅ Finished {table_key} → {txt_log.name}")


# Global SOURCE_NUMBERS
SOURCE_NUMBERS = [s.strip() for s in os.getenv("SOURCE_NUMBERS", "").split(",") if s.strip()]