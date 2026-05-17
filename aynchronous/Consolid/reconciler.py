"""
reconciler.py
=============
Core reconciliation engine.

Reads everything it needs from a script_configs/<table>.json file:
  - Oracle base_query + where_clause
  - Postgres base_query + where_clause
  - How to group rows (group_by_column)
  - Which column in Oracle pairs with which column in Postgres (column_mapping)
  - Which column is the unique match key per row (match_key)

The WHERE clause is a template with {ENV_VAR} placeholders.
The script resolves them from environment variables, turning
comma‑separated values into SQL IN‑lists automatically.

Adding a new table:
  1. Create script_configs/<newtable>.json
  2. DB expert fills in base_query and where_clause
  3. Run:  python runner.py --tables newtable
  No Python changes needed.
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
        for key in ("base_query", "group_by_column", "match_key"):
            if key not in cfg[side]:
                raise ValueError(f"Config [{side}] missing '{key}' in {config_path}")

    return cfg


# ─────────────────────────── WHERE clause resolver ───────────────────────────
def resolve_where_clause(where_clause: str) -> tuple[str, dict]:
    """
    Replace all {ENV_VAR} placeholders with properly quoted SQL values.
    Returns (resolved_where_string, dict_of_placeholder_values).
    If the environment variable contains commas, each item is individually quoted
    (suitable for IN lists). Otherwise the whole value is single‑quoted.
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
        # If the value contains commas, treat as list of items → each quoted
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
    Type-aware comparison.
      - Both None           → equal
      - One None, other ""  → equal  (handles Oracle NULL vs Postgres empty string)
      - Numeric types       → Decimal comparison, tolerance 0.000001
      - Date/timestamp      → compare up to seconds (microseconds stripped)
      - Everything else     → case-insensitive string comparison
    """
    if a is None and b is None:
        return True

    # Treat None ↔ empty string as equal
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
    """
    Group rows into a dict keyed by the group column value.
    group_col is matched case-insensitively against col_names.
    Keys are stripped strings to avoid whitespace mismatches.
    """
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


# ─────────────────────────── Row matching ────────────────────────────────────
def match_rows(oracle_rows: list, postgres_rows: list, match_key: str) -> list:
    """
    Match Oracle rows to Postgres rows using the unique match key column.
    Returns a list of (oracle_row | None, postgres_row | None) tuples.
    """
    def key_val(row, col):
        return str(row.get(col.upper(), "")).strip()

    ora_index  = {key_val(r, match_key): r for r in oracle_rows   if key_val(r, match_key)}
    pg_index   = {key_val(r, match_key): r for r in postgres_rows if key_val(r, match_key)}

    # If neither side has the key, fall back to positional
    if not ora_index and not pg_index:
        pairs = []
        max_len = max(len(oracle_rows), len(postgres_rows))
        for i in range(max_len):
            pairs.append((
                oracle_rows[i]   if i < len(oracle_rows)   else None,
                postgres_rows[i] if i < len(postgres_rows) else None,
            ))
        return pairs

    all_keys = sorted(set(ora_index.keys()) | set(pg_index.keys()))
    return [(ora_index.get(k), pg_index.get(k)) for k in all_keys]


# ─────────────────────────── Column comparison ───────────────────────────────
def compare_row_pair(
    o_row: dict | None,
    p_row: dict | None,
    column_mapping: dict,
) -> tuple[dict, dict]:
    """
    Compare one Oracle row against one Postgres row using column_mapping.
    Returns (mismatches_dict, renamed_matches_dict).
    """
    mismatches = {}
    renamed_matches = {}

    if o_row is None or p_row is None:
        return mismatches, renamed_matches

    for pg_col, col_cfg in column_mapping.items():
        if col_cfg.get("skip_compare"):
            continue

        ora_col   = col_cfg.get("oracle_col") or pg_col
        pg_type   = col_cfg.get("pg_type")
        ora_type  = col_cfg.get("ora_type")
        is_renamed = pg_col.upper() != ora_col.upper()

        pg_val  = p_row.get(pg_col.upper())
        ora_val = o_row.get(ora_col.upper())

        if not values_equal(pg_val, ora_val, pg_type, ora_type):
            mismatches[pg_col] = {
                "alloydb_value": pg_val,
                "alloydb_type":  pg_type,
                "onprem_value":  ora_val,
                "onprem_column": ora_col,
                "onprem_type":   ora_type,
                "derived":       col_cfg.get("derived_in_oracle", False),
            }
        elif is_renamed:
            renamed_matches[pg_col] = {
                "alloydb_value": pg_val,
                "onprem_value":  ora_val,
                "onprem_column": ora_col,
            }

    return mismatches, renamed_matches


# ─────────────────────────── Main reconcile ──────────────────────────────────
def reconcile(config_path: str, output_dir: str = "reports") -> dict:
    """
    Full reconciliation for one table.
    Reads config, builds final SQL from base + where, compares, writes reports.
    Produces a JSON report in the style of the invoice reconciler.
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
    oracle_sql, oracle_vals = build_final_query(cfg["oracle"]["base_query"], cfg["oracle"].get("where_clause", ""))
    postgres_sql, postgres_vals = build_final_query(cfg["postgres"]["base_query"], cfg["postgres"].get("where_clause", ""))

    # Combine filter values from both sides (usually identical, but safe)
    filter_values = {}
    filter_values.update(oracle_vals)
    filter_values.update(postgres_vals)

    logger.info("Starting reconciliation for %s", table)

    # ── Report skeleton (invoice style) ────────────────────────────────────────
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
    log(f"  Oracle WHERE : {cfg['oracle'].get('where_clause', 'none')}")
    log(f"  Postgres WHERE: {cfg['postgres'].get('where_clause', 'none')}")
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

        # ── Group ──────────────────────────────────────────────────────────────
        oracle_grouped   = group_rows(ora_cols, ora_rows, cfg["oracle"]["group_by_column"])
        postgres_grouped = group_rows(pg_cols,  pg_rows,  cfg["postgres"]["group_by_column"])

        all_keys      = set(oracle_grouped) | set(postgres_grouped)
        common_keys   = set(oracle_grouped) & set(postgres_grouped)
        missing_in_pg = sorted(set(oracle_grouped)   - set(postgres_grouped))
        missing_in_ora = sorted(set(postgres_grouped) - set(oracle_grouped))

        report["missing_in_oracle"]   = missing_in_ora
        report["missing_in_postgres"] = missing_in_pg

        if missing_in_pg:
            log(f"\n⚠️  Keys in Oracle but NOT in Postgres ({len(missing_in_pg)}): {missing_in_pg}")
        if missing_in_ora:
            log(f"\n⚠️  Keys in Postgres but NOT in Oracle ({len(missing_in_ora)}): {missing_in_ora}")

        col_mapping   = cfg["column_mapping"]
        ora_match_key = cfg["oracle"]["match_key"]
        pg_match_key  = cfg["postgres"]["match_key"]

        mismatches_by_sn = {}
        renamed_comp = {}

        for group_key in sorted(common_keys):
            o_rows_grp = oracle_grouped[group_key]
            p_rows_grp = postgres_grouped[group_key]

            log(f"\n📊 Group key: {group_key}  |  Oracle rows: {len(o_rows_grp)}  Postgres rows: {len(p_rows_grp)}")

            pairs = match_rows(o_rows_grp, p_rows_grp, ora_match_key)

            for o_row, p_row in pairs:
                if o_row is None:
                    pk = p_row.get(pg_match_key.upper(), "?")
                    log(f"   ⚠️  Row key={pk} exists in Postgres but not in Oracle")
                    mismatches_by_sn[f"{group_key}_{pk}"] = {
                        "group_key": group_key,
                        "row_identifier": pk,
                        "mismatch_count": 1,
                        "columns": {
                            "only_in_postgres": {
                                "alloydb_value": "ROW PRESENT",
                                "onprem_value": "MISSING",
                                "onprem_column": "",
                                "onprem_type": ""
                            }
                        }
                    }
                    continue
                if p_row is None:
                    pk = o_row.get(ora_match_key.upper(), "?")
                    log(f"   ⚠️  Row key={pk} exists in Oracle but not in Postgres")
                    mismatches_by_sn[f"{group_key}_{pk}"] = {
                        "group_key": group_key,
                        "row_identifier": pk,
                        "mismatch_count": 1,
                        "columns": {
                            "only_in_oracle": {
                                "alloydb_value": "MISSING",
                                "onprem_value": "ROW PRESENT",
                                "onprem_column": "",
                                "onprem_type": ""
                            }
                        }
                    }
                    continue

                mismatches, renamed = compare_row_pair(o_row, p_row, col_mapping)
                pk = str(o_row.get(ora_match_key.upper(), "?"))

                if mismatches:
                    mismatches_by_sn[f"{group_key}_{pk}"] = {
                        "group_key": group_key,
                        "row_identifier": pk,
                        "mismatch_count": len(mismatches),
                        "columns": mismatches,
                    }
                    log(f"   🔴 MISMATCH  row_key={pk}  ({len(mismatches)} columns differ)")
                    for col, diff in mismatches.items():
                        derived_tag = " [DERIVED]" if diff.get("derived") else ""
                        log(
                            f"     • {col:35}{derived_tag}"
                            f"  AlloyDB({diff['alloydb_type']}): {diff['alloydb_value']}"
                            f"  |  Oracle({diff['onprem_type']}) [{diff['onprem_column']}]: {diff['onprem_value']}"
                        )
                else:
                    log(f"   ✅ row_key={pk}  matches")

                if renamed:
                    renamed_comp[f"{group_key}_{pk}"] = {
                        "group_key": group_key,
                        "row_identifier": pk,
                        "columns": renamed,
                    }

        report["mismatches_by_sourcenumber"] = mismatches_by_sn
        report["renamed_columns_comparison"] = renamed_comp

        # ── Summary ────────────────────────────────────────────────────────────
        log(f"\n{'='*140}")
        log("FINAL SUMMARY")
        log(f"{'='*140}")
        log(f"  Total group keys compared    : {len(common_keys)}")
        log(f"  Total mismatches found       : {len(mismatches_by_sn)}")
        log(f"  Missing in Postgres          : {len(missing_in_pg)}")
        log(f"  Missing in Oracle            : {len(missing_in_ora)}")
        log(f"  Oracle rows fetched          : {report['oracle_row_count']}")
        log(f"  Postgres rows fetched        : {report['postgres_row_count']}")
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

    return report