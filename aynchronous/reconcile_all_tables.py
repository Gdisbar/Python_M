#!/usr/bin/env python3
"""
Generic Oracle ↔ Postgres reconciliation for multiple tables,
filtered by SOURCENUMBER values.
"""

import os
import sys
import json
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict
from datetime import datetime

import oracledb
import psycopg2
from dotenv import load_dotenv

# Import normalisation and mismatch classes from existing module
from reconcile_runner_v2 import Normalizer, ColumnDiff, RowMismatch, C, _c, print_report

load_dotenv()

# =============================================================================
# Table list (Oracle uppercase, Postgres lowercase)
TABLES = [
    "charge", "chargelineitem", "discount", "discountlineitem",
    "invoice", "invoicedetail", "salestran", "salestrandetail",
    "shipment", "shipmentcontainer", "shipmentcontainerdetail",
    "shipmentline", "tenderlineitem"
]

# Source numbers from environment
SOURCE_NUMBERS = [s.strip() for s in os.getenv("SOURCE_NUMBERS", "").split(",") if s.strip()]
if not SOURCE_NUMBERS:
    print("❌ No SOURCE_NUMBERS defined in .env")
    sys.exit(1)

# =============================================================================
# Database clients (simplified, no connection pooling for clarity)
class OracleClient:
    def __init__(self):
        self.conn = oracledb.connect(
            user=os.getenv("ORACLE_USER"),
            password=os.getenv("ORACLE_PASSWORD"),
            dsn=os.getenv("ORACLE_DSN")
        )
        self.cursor = self.conn.cursor()

    def get_primary_key(self, table: str) -> str:
        """Try to find a reasonable primary key column."""
        # Query all constraints for primary key
        sql = """
        SELECT cols.column_name
        FROM all_constraints cons, all_cons_columns cols
        WHERE cons.owner = 'CEX01_OWN'
          AND cons.constraint_type = 'P'
          AND cons.constraint_name = cols.constraint_name
          AND cons.owner = cols.owner
          AND cols.table_name = UPPER(:t)
        """
        self.cursor.execute(sql, t=table)
        row = self.cursor.fetchone()
        if row:
            return row[0].lower()   # return lowercase for consistency
        # Fallback: guess 'id' or '<table>_id'
        candidates = ['id', f"{table}_id"]
        for cand in candidates:
            try:
                self.cursor.execute(f"SELECT {cand} FROM CEX01_OWN.{table} WHERE ROWNUM=1")
                return cand
            except oracledb.Error:
                continue
        raise RuntimeError(f"Cannot determine primary key for table {table}")

    def fetch_rows(self, table: str, pk_column: str, source_numbers: List[str]) -> List[Tuple]:
        """Fetch all rows where SOURCENUMBER IN (...)"""
        placeholders = ','.join([f"'{sn}'" for sn in source_numbers])
        sql = f"""
        SELECT * FROM CEX01_OWN.{table}
        WHERE SOURCENUMBER IN ({placeholders})
        ORDER BY {pk_column}
        """
        self.cursor.execute(sql)
        return self.cursor.fetchall()

    def get_column_names(self, table: str) -> List[str]:
        self.cursor.execute(f"SELECT * FROM CEX01_OWN.{table} WHERE ROWNUM=0")
        return [desc[0].lower() for desc in self.cursor.description]

    def close(self):
        self.cursor.close()
        self.conn.close()


class PostgresClient:
    def __init__(self):
        self.conn = psycopg2.connect(
            host=os.getenv("PG_HOST"),
            port=os.getenv("PG_PORT", "5432"),
            dbname=os.getenv("PG_DATABASE"),
            user=os.getenv("PG_USER"),
            password=os.getenv("PG_PASSWORD")
        )
        self.cursor = self.conn.cursor()

    def get_primary_key(self, table: str) -> str:
        """Query pg_constraint for primary key."""
        sql = """
        SELECT a.attname
        FROM   pg_index i
        JOIN   pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
        WHERE  i.indrelid = 'sba_own.' || %s::regclass
          AND  i.indisprimary
        """
        self.cursor.execute(sql, (table,))
        row = self.cursor.fetchone()
        if row:
            return row[0]
        # Fallback
        candidates = ['id', f"{table}_id"]
        for cand in candidates:
            try:
                self.cursor.execute(f"SELECT {cand} FROM sba_own.{table} LIMIT 1")
                return cand
            except psycopg2.Error:
                continue
        raise RuntimeError(f"Cannot determine primary key for table {table}")

    def fetch_rows(self, table: str, pk_column: str, source_numbers: List[str]) -> List[Tuple]:
        placeholders = ','.join([f"'{sn}'" for sn in source_numbers])
        sql = f"""
        SELECT * FROM sba_own.{table}
        WHERE sourcenumber IN ({placeholders})
        ORDER BY {pk_column}
        """
        self.cursor.execute(sql)
        return self.cursor.fetchall()

    def get_column_names(self, table: str) -> List[str]:
        self.cursor.execute(f"SELECT * FROM sba_own.{table} LIMIT 0")
        return [desc[0].lower() for desc in self.cursor.description]

    def close(self):
        self.cursor.close()
        self.conn.close()


# =============================================================================
# Generic reconciliation engine (refactored from original)
class GenericReconciliationEngine:
    def __init__(self, amount_tolerance: float = 0.01, text_similarity_warn: float = 0.92,
                 use_hash_prescreen: bool = True):
        self.amount_tolerance = Decimal(str(amount_tolerance))
        self.text_similarity_warn = text_similarity_warn
        self.use_hash_prescreen = use_hash_prescreen

    def compare(self, oracle_rows: List[Tuple], postgres_rows: List[Tuple],
                columns: List[str], pk_column: str) -> 'ReconciliationResult':
        """Compare two row sets with known column list and primary key."""
        from reconcile_runner_v2 import ReconciliationResult  # avoid circular import

        result = ReconciliationResult(
            total_oracle_rows=len(oracle_rows),
            total_postgres_rows=len(postgres_rows)
        )
        pk_idx = columns.index(pk_column)

        pg_dict = {row[pk_idx]: row for row in postgres_rows}
        oracle_dict = {row[pk_idx]: row for row in oracle_rows}

        # Oracle -> Postgres
        for pk, o_row in oracle_dict.items():
            if pk not in pg_dict:
                result.missing_in_postgres.append(str(pk))
                continue
            p_row = pg_dict[pk]
            # fast hash pre‑screen
            if self.use_hash_prescreen and self._row_hash(o_row, columns) == self._row_hash(p_row, columns):
                result.rows_skipped_identical += 1
                continue
            diffs = self._compare_rows(o_row, p_row, columns)
            if diffs:
                result.mismatches.append(RowMismatch(order_id=str(pk), column_diffs=diffs))
            else:
                result.rows_skipped_identical += 1

        # Postgres -> Oracle (ghosts)
        for pk in pg_dict:
            if pk not in oracle_dict:
                result.missing_in_oracle.append(str(pk))

        # sort mismatches by severity
        sev_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
        result.mismatches.sort(key=lambda rm: sev_order[rm.severity])
        return result

    def _row_hash(self, row: Tuple, columns: List[str]) -> str:
        """SHA256 of normalised values (same as original)."""
        import hashlib
        canonical = "|".join(
            "" if v is None else
            Decimal(str(v)).quantize(Decimal("0.01")).__str__() if isinstance(v, (int, float, Decimal)) else
            str(v).strip().lower()
            for v in row
        )
        return hashlib.sha256(canonical.encode()).hexdigest()

    def _compare_rows(self, o_row: Tuple, p_row: Tuple, columns: List[str]) -> List[ColumnDiff]:
        diffs = []
        for idx, col in enumerate(columns):
            o_val, p_val = o_row[idx], p_row[idx]
            cd = self._compare_column(col, o_val, p_val)
            if cd:
                diffs.append(cd)
        return diffs

    def _compare_column(self, col: str, o_val: Any, p_val: Any) -> Optional[ColumnDiff]:
        # Detect type by inspecting values
        if isinstance(o_val, (int, float, Decimal)) and isinstance(p_val, (int, float, Decimal)):
            # numeric
            o_n = Normalizer.normalize_numeric(o_val)
            p_n = Normalizer.normalize_numeric(p_val)
            if o_n == p_n:
                return None
            delta = abs(o_n - p_n) if o_n is not None and p_n is not None else None
            if delta is not None and delta <= self.amount_tolerance:
                return ColumnDiff(col, o_val, p_val, "amount_rounding_noise", "INFO",
                                  f"Δ={delta} within tolerance")
            severity = "CRITICAL" if (delta and delta > Decimal("1.00")) else "WARNING"
            return ColumnDiff(col, o_val, p_val, "amount_drift", severity, f"Δ={delta}")

        elif isinstance(o_val, datetime) or isinstance(p_val, datetime):
            o_n = Normalizer.normalize_timestamp(o_val)
            p_n = Normalizer.normalize_timestamp(p_val)
            if o_n == p_n:
                return None
            tz_delta = Normalizer.timestamp_tz_delta(o_n, p_n)
            if tz_delta is not None:
                return ColumnDiff(col, o_val, p_val, "timezone_shift", "WARNING",
                                  f"Offset {tz_delta//3600:+d}h")
            return ColumnDiff(col, o_val, p_val, "timestamp_mismatch", "CRITICAL", "")

        else:
            # string-like comparison
            o_n = Normalizer.normalize_string(o_val)
            p_n = Normalizer.normalize_string(p_val)
            if o_n == p_n:
                return None
            if (o_n or "").lower() == (p_n or "").lower():
                return ColumnDiff(col, o_val, p_val, "case_mismatch", "INFO",
                                  f"Ignoring case: '{o_val}' vs '{p_val}'")
            # optional: text similarity for long strings
            if isinstance(o_val, str) and isinstance(p_val, str) and len(o_val) > 20:
                sim = Normalizer.text_similarity(o_val, p_val)
                if sim >= self.text_similarity_warn:
                    return ColumnDiff(col, o_val, p_val, "near_match_text", "WARNING",
                                      f"Similarity {sim:.1%}")
            return ColumnDiff(col, o_val, p_val, "value_mismatch", "CRITICAL",
                              f"'{o_val}' ≠ '{p_val}'")


# =============================================================================
# Main orchestration
def reconcile_table(engine: GenericReconciliationEngine,
                    oracle: OracleClient, pg: PostgresClient,
                    table: str, source_numbers: List[str]):
    print(f"\n{_c(C.BOLD, f'>>> Processing table: {table}')}")
    # Get column names (same order on both sides)
    oracle_cols = oracle.get_column_names(table)
    pg_cols = pg.get_column_names(table)
    if set(oracle_cols) != set(pg_cols):
        print(f"  ⚠️ Column mismatch: Oracle {oracle_cols} vs Postgres {pg_cols}")
        # Continue but only compare common columns
        common_cols = [c for c in oracle_cols if c in pg_cols]
        if not common_cols:
            print("  ❌ No common columns, skipping")
            return
    else:
        common_cols = oracle_cols

    # Primary key
    pk = oracle.get_primary_key(table)   # same on PG after lowercasing
    if pk not in common_cols:
        print(f"  ❌ Primary key '{pk}' not in common columns, skipping")
        return

    # Fetch rows
    oracle_rows = oracle.fetch_rows(table, pk, source_numbers)
    pg_rows = pg.fetch_rows(table, pk, source_numbers)

    # Reorder rows to match common_cols order (Oracle and PG may have same columns but different order)
    # We'll map each row to a tuple in common_cols order
    def reorder(row, cols, full_cols):
        # row is tuple in same order as full_cols (from SELECT *)
        idx_map = {full_cols[i]: i for i in range(len(full_cols))}
        return tuple(row[idx_map[col]] for col in cols)

    oracle_rows_reordered = [reorder(r, common_cols, oracle_cols) for r in oracle_rows]
    pg_rows_reordered = [reorder(r, common_cols, pg_cols) for r in pg_rows]

    # Run reconciliation
    result = engine.compare(oracle_rows_reordered, pg_rows_reordered,
                            columns=common_cols, pk_column=pk)

    # Print & save report
    print_report(result)
    out_file = f"reconciliation_{table}.json"
    with open(out_file, "w") as f:
        json.dump(result.to_dict(), f, indent=2, default=str)
    print(f"  📄 Detailed report saved to {out_file}")


def main():
    print(_c(C.BOLD + C.CYAN, "\n🔁 Starting multi‑table reconciliation"))
    print(f"Source numbers: {SOURCE_NUMBERS}")
    print(f"Tables: {', '.join(TABLES)}")

    oracle = OracleClient()
    pg = PostgresClient()
    engine = GenericReconciliationEngine(amount_tolerance=0.01, text_similarity_warn=0.92)

    for table in TABLES:
        try:
            reconcile_table(engine, oracle, pg, table, SOURCE_NUMBERS)
        except Exception as e:
            print(_c(C.RED, f"  ❌ Error on {table}: {e}"))
            continue

    oracle.close()
    pg.close()
    print(_c(C.GREEN, "\n✅ Reconciliation completed.\n"))

if __name__ == "__main__":
    main()