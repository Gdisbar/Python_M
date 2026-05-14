#!/usr/bin/env python3
"""
Simple Oracle ↔ Postgres reconciliation for multiple tables,
filtered by SOURCENUMBER values.
"""

import os
import sys
import json
from typing import List, Tuple, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime

import oracledb
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# Configuration from .env
# ============================================================================
SOURCE_NUMBERS = [s.strip() for s in os.getenv("SOURCE_NUMBERS", "").split(",") if s.strip()]
if not SOURCE_NUMBERS:
    print("❌ No SOURCE_NUMBERS defined in .env")
    sys.exit(1)

ORACLE_USER = os.getenv("ORACLE_USER")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD")
ORACLE_DSN = os.getenv("ORACLE_DSN")          # e.g. "host:1521/service_name"

PG_HOST = os.getenv("PG_HOST")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_DATABASE = os.getenv("PG_DATABASE")
PG_USER = os.getenv("PG_USER")
PG_PASSWORD = os.getenv("PG_PASSWORD")

# Tables to reconcile (Oracle uppercase, Postgres lowercase)
TABLES = [
    "charge", "chargelineitem", "discount", "discountlineitem",
    "invoice", "invoicedetail", "salestran", "salestrandetail",
    "shipment", "shipmentcontainer", "shipmentcontainerdetail",
    "shipmentline", "tenderlineitem"
]

# ============================================================================
# Database helpers
# ============================================================================
def get_oracle_connection():
    return oracledb.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=ORACLE_DSN)

def get_postgres_connection():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DATABASE,
        user=PG_USER, password=PG_PASSWORD
    )

def get_primary_key_oracle(conn, table: str) -> str:
    """Return primary key column name for Oracle table."""
    cursor = conn.cursor()
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
    cursor.execute(sql, t=table)
    row = cursor.fetchone()
    cursor.close()
    if row:
        return row[0].lower()
    # Fallback: guess 'id' or 'tablename_id'
    candidates = ['id', f"{table}_id"]
    for cand in candidates:
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT {cand} FROM CEX01_OWN.{table} WHERE ROWNUM=1")
            cursor.close()
            return cand
        except:
            continue
    raise RuntimeError(f"Cannot find primary key for {table}")

def get_primary_key_postgres(conn, table: str) -> str:
    """Return primary key column name for Postgres table."""
    cursor = conn.cursor()
    sql = """
    SELECT a.attname
    FROM pg_index i
    JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
    WHERE i.indrelid = ('sba_own.' || %s)::regclass AND i.indisprimary
    """
    cursor.execute(sql, (table,))
    row = cursor.fetchone()
    cursor.close()
    if row:
        return row[0]
    candidates = ['id', f"{table}_id"]
    for cand in candidates:
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT {cand} FROM sba_own.{table} LIMIT 1")
            cursor.close()
            return cand
        except:
            continue
    raise RuntimeError(f"Cannot find primary key for {table}")

def fetch_oracle_rows(conn, table: str, pk: str, source_numbers: List[str]) -> Dict[Any, Tuple]:
    """Return dict {pk_value: row_tuple} for rows matching SOURCENUMBER."""
    placeholders = ','.join([f"'{sn}'" for sn in source_numbers])
    sql = f"""
    SELECT * FROM CEX01_OWN.{table}
    WHERE SOURCENUMBER IN ({placeholders})
    """
    cursor = conn.cursor()
    cursor.execute(sql)
    cols = [desc[0].lower() for desc in cursor.description]
    rows = cursor.fetchall()
    cursor.close()
    pk_idx = cols.index(pk)
    return {row[pk_idx]: (cols, row) for row in rows}

def fetch_postgres_rows(conn, table: str, pk: str, source_numbers: List[str]) -> Dict[Any, Tuple]:
    """Return dict {pk_value: row_tuple} for rows matching SOURCENUMBER."""
    placeholders = ','.join([f"'{sn}'" for sn in source_numbers])
    sql = f"""
    SELECT * FROM sba_own.{table}
    WHERE sourcenumber IN ({placeholders})
    """
    cursor = conn.cursor()
    cursor.execute(sql)
    cols = [desc[0].lower() for desc in cursor.description]
    rows = cursor.fetchall()
    cursor.close()
    pk_idx = cols.index(pk)
    return {row[pk_idx]: (cols, row) for row in rows}

# ============================================================================
# Comparison logic (simple value equality)
# ============================================================================
def values_equal(a: Any, b: Any) -> bool:
    """Compare two values, handling None, Decimal, datetime."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    # Normalise numeric types
    if isinstance(a, (int, float, Decimal)) and isinstance(b, (int, float, Decimal)):
        return Decimal(str(a)) == Decimal(str(b))
    # Normalise datetime (ignore timezone)
    if isinstance(a, datetime) and isinstance(b, datetime):
        return a.replace(tzinfo=None) == b.replace(tzinfo=None)
    # String comparison
    return str(a).strip() == str(b).strip()

def compare_rows(oracle_row: Tuple, oracle_cols: List[str],
                 postgres_row: Tuple, postgres_cols: List[str]) -> List[Dict]:
    """Return list of mismatches with column name and both values."""
    # Build a dict of oracle values by column name
    oracle_dict = {col: oracle_row[i] for i, col in enumerate(oracle_cols)}
    postgres_dict = {col: postgres_row[i] for i, col in enumerate(postgres_cols)}
    
    # Use all columns from Oracle (we assume they exist in Postgres, else skip)
    mismatches = []
    for col in oracle_cols:
        if col not in postgres_dict:
            mismatches.append({
                "column": col,
                "oracle": oracle_dict[col],
                "postgres": "<column missing in Postgres>"
            })
            continue
        o_val = oracle_dict[col]
        p_val = postgres_dict[col]
        if not values_equal(o_val, p_val):
            mismatches.append({
                "column": col,
                "oracle": o_val,
                "postgres": p_val
            })
    return mismatches

# ============================================================================
# Main reconciliation for one table
# ============================================================================
def reconcile_table(table: str, source_numbers: List[str]):
    print(f"\n--- Processing table: {table} ---")
    
    ora_conn = get_oracle_connection()
    pg_conn = get_postgres_connection()
    
    try:
        # Get primary key (must be same name in both DBs)
        pk = get_primary_key_oracle(ora_conn, table)
        # Verify Postgres has same primary key (optional, but we trust)
        
        # Fetch rows
        oracle_rows = fetch_oracle_rows(ora_conn, table, pk, source_numbers)
        pg_rows = fetch_postgres_rows(pg_conn, table, pk, source_numbers)
        
        print(f"  Oracle rows: {len(oracle_rows)} | Postgres rows: {len(pg_rows)}")
        
        # Compare matching primary keys
        all_pks = set(oracle_rows.keys()) | set(pg_rows.keys())
        mismatches_by_pk = {}
        
        for pk_val in all_pks:
            o_data = oracle_rows.get(pk_val)
            p_data = pg_rows.get(pk_val)
            
            if o_data is None:
                mismatches_by_pk[pk_val] = {"status": "missing_in_oracle", "diffs": []}
                continue
            if p_data is None:
                mismatches_by_pk[pk_val] = {"status": "missing_in_postgres", "diffs": []}
                continue
            
            oracle_cols, oracle_row = o_data
            pg_cols, pg_row = p_data
            diffs = compare_rows(oracle_row, oracle_cols, pg_row, pg_cols)
            if diffs:
                mismatches_by_pk[pk_val] = {"status": "mismatch", "diffs": diffs}
        
        # Output results
        if not mismatches_by_pk:
            print("  ✅ All rows match perfectly.")
        else:
            print(f"  ⚠️ Found {len(mismatches_by_pk)} rows with issues.")
            for pk_val, info in mismatches_by_pk.items():
                print(f"\n    Primary key: {pk_val}  [{info['status']}]")
                for diff in info['diffs']:
                    print(f"      {diff['column']}:")
                    print(f"        CEX01_OWN.{diff['column']} : {diff['oracle']}")
                    print(f"        sba_own.{diff['column']}   : {diff['postgres']}")
        
        # Save JSON report
        report = {
            "table": table,
            "source_numbers": source_numbers,
            "oracle_rows": len(oracle_rows),
            "postgres_rows": len(pg_rows),
            "issues": mismatches_by_pk
        }
        with open(f"report_{table}.json", "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"  📄 Detailed report saved to report_{table}.json")
        
    finally:
        ora_conn.close()
        pg_conn.close()

# ============================================================================
# Main
# ============================================================================
def main():
    print("🔁 Simple reconciliation started")
    print(f"Source numbers: {SOURCE_NUMBERS}")
    for table in TABLES:
        try:
            reconcile_table(table, SOURCE_NUMBERS)
        except Exception as e:
            print(f"  ❌ Error on {table}: {e}")
    print("\n✅ Done.")

if __name__ == "__main__":
    main()
