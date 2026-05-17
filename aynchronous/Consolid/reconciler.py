"""
reconciler.py
=============
Config‑driven reconciliation engine.
Uses base_query + where_clause from JSON, resolves {ENV_VAR} placeholders,
fetches data from Oracle and Postgres, then compares every pair of rows
within each group (identified by group_by_column). Outputs a report in
the same style as the standalone chargelineitem script.

Adding a new table:
  1. Create script_configs/<newtable>.json with base_query + where_clause
  2. Set the required environment variables
  3. Run: python runner.py --tables newtable
"""

import os
import re
import json
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import unicodedata

import oracledb
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────── Logging ────────────────────────────────────────
def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


# ─────────────────────────── Config loader ──────────────────────────────────
def load_config(config_path: str) -> dict:
    """Load and validate a table JSON config file."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)

    required_top = {"table_name", "oracle", "postgres", "column_mapping"}
    missing = required_top - set(cfg.keys())
    if missing:
        raise ValueError(f"Config {config_path} missing keys: {missing}")

    for side in ("oracle", "postgres"):
        for key in ("base_query", "group_by_column"):
            if key not in cfg[side]:
                raise ValueError(f"Config [{side}] missing '{key}' in {config_path}")

    return cfg


# ─────────────────────────── WHERE clause resolver ───────────────────────────
def resolve_where_clause(where_clause: str) -> tuple[str, dict]:
    """
    Replace all {ENV_VAR} placeholders with properly quoted SQL values.
    Returns (resolved_where_string, dict_of_placeholder_values).
    Comma‑separated env values become individually quoted for IN lists.
    """
    if not where_clause.strip():
        return "", {}

    placeholders = re.findall(r'\{(\w+)\}', where_clause)
    resolved = where_clause
    values = {}
    for ph in placeholders:
        value = os.getenv(ph)
        if value is None:
            raise ValueError(f"Environment variable '{ph}' is not set (needed for WHERE clause).")
        if ',' in value:
            items = [item.strip() for item in value.split(',') if item.strip()]
            replacement = ','.join(f"'{item}'" for item in items)
            values[ph] = items
        else:
            replacement = f"'{value.strip()}'"
            values[ph] = value.strip()
        resolved = resolved.replace(f'{{{ph}}}', replacement)
    return resolved, values


def build_final_query(base_query: str, where_clause: str) -> tuple[str, dict]:
    """Combine base query with resolved WHERE clause. Returns (sql, values_dict)."""
    base = base_query.strip()
    if not base:
        raise ValueError("base_query is empty.")
    where_str, values = resolve_where_clause(where_clause)
    if where_str:
        return f"{base} WHERE {where_str}", values
    return base, values


# ─────────────────────────── DB helpers ─────────────────────────────────────
def _oracle_conn():
    return oracledb.connect(
        user=os.getenv("ORACLE_USER"),
        password=os.getenv("ORACLE_PASSWORD"),
        dsn=os.getenv("ORACLE_DSN"),
    )


def _postgres_conn():
    return psycopg2.connect(
        host=os.getenv("PG_HOST"),
        port=os.getenv("PG_PORT", "5432"),
        dbname=os.getenv("PG_DATABASE"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
    )


def _run_query(conn, sql: str) -> tuple[list, list]:
    """Execute SQL and return (column_names_upper, rows)."""
    cur = conn.cursor()
    cur.execute(sql)
    col_names = [desc[0].upper() for desc in cur.description]
    rows = cur.fetchall()
    cur.close()
    return col_names, rows


def fetch_oracle(sql: str) -> tuple[list, list]:
    conn = _oracle_conn()
    try:
        return _run_query(conn, sql)
    finally:
        conn.close()


def fetch_postgres(sql: str) -> tuple[list, list]:
    conn = _postgres_conn()
    try:
        return _run_query(conn, sql)
    finally:
        conn.close()


# ─────────────────────────── Value comparison ────────────────────────────────
def normalize_value(val):
    if isinstance(val, str):
        return unicodedata.normalize("NFKC", val.strip())
    return val


def values_equal(a, b, pg_type: str = None, ora_type: str = None) -> bool:
    """
    Type‑aware comparison.
      - Both None           → equal
      - One None, other ""  → equal (Oracle NULL vs Postgres empty string)
      - Numeric types       → Decimal comparison, tolerance 0.000001
      - Date/timestamp      → compare up to seconds
      - Everything else     → case‑insensitive string comparison
    """
    if a is None and b is None:
        return True
    if a is None:
        return str(b).strip() == ""
    if b is None:
        return str(a).strip() == ""

    a = normalize_value(a)
    b = normalize_value(b)

    type_tags = [str(t).lower() for t in [pg_type, ora_type] if t]

    try:
        is_numeric = any(
            tag and any(kw in tag for kw in ("numeric", "int8", "int4", "number", "decimal", "float"))
            for tag in type_tags
        )
        is_datetime = any(
            tag and any(kw in tag for kw in ("timestamp", "time", "date"))
            for tag in type_tags
        )

        if is_numeric:
            da = Decimal(str(a))
            db = Decimal(str(b))
            return abs(da - db) <= Decimal("0.000001")
        if is_datetime:
            if isinstance(a, datetime) and isinstance(b, datetime):
                return a.replace(microsecond=0) == b.replace(microsecond=0)
            return str(a)[:19] == str(b)[:19]
        return str(a).strip().lower() == str(b).strip().lower()
    except (InvalidOperation, Exception):
        return str(a).strip().lower() == str(b).strip().lower()


# ─────────────────────────── Row grouping ────────────────────────────────────
def group_rows(col_names: list, rows: list, group_col: str) -> dict:
    """Group rows into a dict keyed by the group column value (case‑insensitive)."""
    col_upper = [c.upper() for c in col_names]
    try:
        idx = col_upper.index(group_col.upper())
    except ValueError:
        raise ValueError(
            f"group_by_column '{group_col}' not found in result columns: {col_names}"
        )

    grouped = {}
    for row in rows:
        key = str(row[idx]).strip()
        grouped.setdefault(key, []).append(dict(zip(col_upper, row)))
    return grouped


# ─────────────────────────── Main reconcile ──────────────────────────────────
def reconcile(config_path: str, output_dir: str = "reports") -> dict:
    """
    Full reconciliation for one table – all‑pairs comparison per group.
    Output format matches the chargelineitem standalone script.
    """
    cfg    = load_config(config_path)
    table  = cfg["table_name"]
    logger = get_logger(f"reconciler.{table}")

    # ── Output paths ──────────────────────────────────────────────────────────
    txt_dir  = Path(output_dir) / "txt_reports"
    json_dir = Path(output_dir) / "json_reports"
    txt_dir.mkdir(parents=True, exist_ok=True)
    json_dir.mkdir(parents=True, exist_ok=True)

    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    txt_path  = txt_dir  / f"reconcile_{table.lower()}_{ts}.txt"
    json_path = json_dir / f"report_{table.lower()}_{ts}.json"

    # ── Build final SQL ───────────────────────────────────────────────────────
    oracle_sql, oracle_vals   = build_final_query(cfg["oracle"]["base_query"],  cfg["oracle"].get("where_clause", ""))
    postgres_sql, postgres_vals = build_final_query(cfg["postgres"]["base_query"], cfg["postgres"].get("where_clause", ""))

    # Merge placeholder values from both sides (usually identical)
    filter_values = {}
    filter_values.update(oracle_vals)
    filter_values.update(postgres_vals)

    logger.info("Starting reconciliation for %s", table)

    # ── Report skeleton (matches chargelineitem style) ─────────────────────────
    report = {
        "table":                   table,
        "config_file":             str(config_path),
        "reconciled_on":           datetime.now().isoformat(),
        "filter_values":           filter_values,
        "oracle_row_count":        0,
        "postgres_row_count":      0,
        "missing_in_oracle":       [],
        "missing_in_postgres":     [],
        "mismatches_by_sourcenumber": {},
        "renamed_columns_comparison": {},
        "errors":                  [],
    }

    lines = []  # collected for txt report

    def log(msg: str):
        lines.append(msg)
        logger.info(msg)

    log(f"{'='*140}")
    log(f"  {table} RECONCILIATION REPORT  (AlloyDB ↔ On-Prem Oracle)")
    log(f"  Run Time     : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"  Filter values: {filter_values}")
    log(f"{'='*140}")

    try:
        # ── Fetch ──────────────────────────────────────────────────────────────
        ora_cols, ora_rows = fetch_oracle(oracle_sql)
        pg_cols,  pg_rows  = fetch_postgres(postgres_sql)

        report["oracle_row_count"]   = len(ora_rows)
        report["postgres_row_count"] = len(pg_rows)
        log(f"  Oracle rows fetched   : {len(ora_rows)}")
        log(f"  Postgres rows fetched : {len(pg_rows)}")

        # ── Group by the group_by_column ───────────────────────────────────────
        oracle_grouped   = group_rows(ora_cols, ora_rows, cfg["oracle"]["group_by_column"])
        postgres_grouped = group_rows(pg_cols,  pg_rows,  cfg["postgres"]["group_by_column"])

        common_keys   = set(oracle_grouped) & set(postgres_grouped)
        missing_in_pg = sorted(set(oracle_grouped)   - set(postgres_grouped))
        missing_in_ora = sorted(set(postgres_grouped) - set(oracle_grouped))

        report["missing_in_oracle"]   = missing_in_ora
        report["missing_in_postgres"] = missing_in_pg

        if missing_in_pg:
            log(f"\n⚠️  Keys in Oracle but NOT in Postgres ({len(missing_in_pg)}): {missing_in_pg}")
        if missing_in_ora:
            log(f"\n⚠️  Keys in Postgres but NOT in Oracle ({len(missing_in_ora)}): {missing_in_ora}")

        col_mapping = cfg["column_mapping"]

        mismatches_by_sn = {}
        renamed_comp     = {}

        for sn in sorted(common_keys):
            o_rows = oracle_grouped[sn]
            p_rows = postgres_grouped[sn]

            log(f"\n📊 Processing SOURCENUMBER: {sn} | Oracle Rows: {len(o_rows)} | Postgres Rows: {len(p_rows)}")

            # Compare every Oracle row against every Postgres row (all-pairs)
            for i, o_row in enumerate(o_rows):
                for j, p_row in enumerate(p_rows):
                    mismatches = {}
                    renamed_comparisons = {}

                    for pg_col, col_cfg in col_mapping.items():
                        if col_cfg.get("skip_compare"):
                            continue

                        ora_col   = col_cfg.get("oracle_col") or pg_col
                        pg_type   = col_cfg.get("pg_type")
                        ora_type  = col_cfg.get("ora_type")
                        is_renamed = pg_col.upper() != ora_col.upper()

                        pg_val  = p_row.get(pg_col.upper())
                        ora_val = o_row.get(ora_col.upper()) if ora_col else None

                        if not values_equal(pg_val, ora_val, pg_type, ora_type):
                            mismatches[pg_col] = {
                                "alloydb_value": pg_val,
                                "alloydb_type":  pg_type,
                                "onprem_value":  ora_val,
                                "onprem_column": ora_col,
                                "onprem_type":   ora_type,
                            }
                        elif is_renamed:
                            renamed_comparisons[pg_col] = {
                                "alloydb_value": pg_val,
                                "onprem_value":  ora_val,
                                "onprem_column": ora_col,
                            }

                    if mismatches:
                        key = f"{sn}_ora{i}_pg{j}"
                        mismatches_by_sn[key] = {
                            "sourcenumber": sn,
                            "oracle_row": i,
                            "postgres_row": j,
                            "mismatch_count": len(mismatches),
                            "columns": mismatches,
                        }
                        log(f"   🔴 MISMATCH (Oracle Row {i}, Postgres Row {j})")
                        for col, diff in mismatches.items():
                            log(f"     • {col:35} | AlloyDB: {diff['alloydb_value']} | On-Prem: {diff['onprem_value']} | {diff['onprem_type']}")
                    # else: no match message printed (to keep output clean)

                    if renamed_comparisons:
                        key = f"{sn}_ora{i}_pg{j}"
                        renamed_comp[key] = {
                            "sourcenumber": sn,
                            "oracle_row": i,
                            "postgres_row": j,
                            "columns": renamed_comparisons,
                        }

        report["mismatches_by_sourcenumber"] = mismatches_by_sn
        report["renamed_columns_comparison"] = renamed_comp

        # ── Summary ────────────────────────────────────────────────────────────
        log(f"\n{'='*140}")
        log("FINAL SUMMARY")
        log(f"{'='*140}")
        log(f"  Total Unique SOURCENUMBERs : {len(common_keys)}")
        log(f"  Total Mismatches Found     : {len(mismatches_by_sn)}")
        log(f"  Missing in Postgres        : {len(missing_in_pg)}")
        log(f"  Missing in Oracle          : {len(missing_in_ora)}")
        log(f"  Oracle rows fetched        : {report['oracle_row_count']}")
        log(f"  Postgres rows fetched      : {report['postgres_row_count']}")
        log(f"\n  📝 TXT  → {txt_path}")
        log(f"  📊 JSON → {json_path}")

    except Exception as exc:
        err_msg = f"❌ Fatal error during reconciliation of {table}: {exc}"
        logger.exception(err_msg)
        report["errors"].append(err_msg)
        lines.append(err_msg)

    # ── Write reports ──────────────────────────────────────────────────────────
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str, ensure_ascii=False)

    report["_txt_path"]  = str(txt_path)
    report["_json_path"] = str(json_path)

    # For the runner summary, also add a 'mismatches' key with the count
    report["mismatches"] = report["mismatches_by_sourcenumber"]
    return report