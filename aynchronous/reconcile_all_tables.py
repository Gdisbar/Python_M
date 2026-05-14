#!/usr/bin/env python3
"""
Simple Oracle ↔ Postgres reconciliation
No primary key – matches by SOURCENUMBER
"""

import os
import sys
import json
from typing import List, Dict, Any
from decimal import Decimal
from datetime import datetime

import oracledb
import psycopg2
from dotenv import load_dotenv

load_dotenv()

SOURCE_NUMBERS = [s.strip() for s in os.getenv("SOURCE_NUMBERS", "").split(",") if s.strip()]
if not SOURCE_NUMBERS:
    print("❌ No SOURCE_NUMBERS defined in .env")
    sys.exit(1)

ORACLE_USER = os.getenv("ORACLE_USER")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD")
ORACLE_DSN = os.getenv("ORACLE_DSN")

PG_HOST = os.getenv("PG_HOST")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_DATABASE = os.getenv("PG_DATABASE")
PG_USER = os.getenv("PG_USER")
PG_PASSWORD = os.getenv("PG_PASSWORD")

TABLES = [
    "charge", "chargelineitem", "discount", "discountlineitem",
    "invoice", "invoicedetail", "salestran", "salestrandetail",
    "shipment", "shipmentcontainer", "shipmentcontainerdetail",
    "shipmentline", "tenderlineitem"
]

def get_oracle_conn():
    return oracledb.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=ORACLE_DSN)

def get_postgres_conn():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DATABASE,
        user=PG_USER, password=PG_PASSWORD
    )

def fetch_oracle_rows(conn, table: str):
    placeholders = ','.join([f"'{sn}'" for sn in SOURCE_NUMBERS])
    sql = f"SELECT * FROM CEX01_OWN.{table} WHERE SOURCENUMBER IN ({placeholders})"
    cur = conn.cursor()
    cur.execute(sql)
    col_names = [desc[0] for desc in cur.description]  # preserve original case
    rows = cur.fetchall()
    cur.close()
    # Find SOURCENUMBER index
    sn_idx = None
    for i, name in enumerate(col_names):
        if name.upper() == 'SOURCENUMBER':
            sn_idx = i
            break
    if sn_idx is None:
        raise ValueError(f"Table {table} has no SOURCENUMBER column")
    result = {}
    for row in rows:
        sn = str(row[sn_idx])
        result[sn] = {'cols': col_names, 'vals': row}
    return result

def fetch_postgres_rows(conn, table: str):
    placeholders = ','.join([f"'{sn}'" for sn in SOURCE_NUMBERS])
    sql = f"SELECT * FROM sba_own.{table} WHERE sourcenumber IN ({placeholders})"
    cur = conn.cursor()
    cur.execute(sql)
    col_names = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    cur.close()
    sn_idx = None
    for i, name in enumerate(col_names):
        if name.lower() == 'sourcenumber':
            sn_idx = i
            break
    if sn_idx is None:
        raise ValueError(f"Table {table} has no sourcenumber column")
    result = {}
    for row in rows:
        sn = str(row[sn_idx])
        result[sn] = {'cols': col_names, 'vals': row}
    return result

def values_equal(a, b):
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if isinstance(a, (int, float, Decimal)) and isinstance(b, (int, float, Decimal)):
        return Decimal(str(a)) == Decimal(str(b))
    if isinstance(a, datetime) and isinstance(b, datetime):
        return a.replace(tzinfo=None) == b.replace(tzinfo=None)
    return str(a).strip() == str(b).strip()


def reconcile_table(table):
    print(f"\n--- Processing table: {table} ---")
    ora_conn = get_oracle_conn()
    pg_conn = get_postgres_conn()
    
    try:
        oracle = fetch_oracle_rows(ora_conn, table)
        postgres = fetch_postgres_rows(pg_conn, table)
       
        print(f" SOURCENUMBER found - Oracle : {len(oracle)} | Postgres : {len(postgres)}")
       
        missing_in_oracle = set(postgres.keys()) - set(oracle.keys())
        missing_in_postgres = set(oracle.keys()) - set(postgres.keys())
       
        if missing_in_oracle:
            print(f" ⚠️ Missing in Oracle: {len(missing_in_oracle)} row(s)")
        if missing_in_postgres:
            print(f" ⚠️ Missing in Postgres: {len(missing_in_postgres)} row(s)")

        report = {
            "table": table,
            "source_numbers": SOURCE_NUMBERS,
            "oracle_row_count": len(oracle),
            "postgres_row_count": len(postgres),
            "missing_in_oracle": list(missing_in_oracle),
            "missing_in_postgres": list(missing_in_postgres),
            "mismatches_by_sourcenumber": {}
        }

        common = set(oracle.keys()) & set(postgres.keys())
        mismatches_found = False

        for sn in common:
            o = oracle[sn]
            p = postgres[sn]
            
            o_dict = {o['cols'][i]: o['vals'][i] for i in range(len(o['cols']))}
            p_dict = {p['cols'][i]: p['vals'][i] for i in range(len(p['cols']))}
            
            row_mismatches = {}
            
            # Check all columns from Oracle + any extra in Postgres
            all_columns = set(o_dict.keys()) | set(p_dict.keys())
            
            for col in sorted(all_columns):
                oval = o_dict.get(col)
                pval = p_dict.get(col)
                
                if col not in p_dict:
                    row_mismatches[col] = {
                        "oracle": oval,
                        "postgres": "<column_missing>"
                    }
                elif col not in o_dict:
                    row_mismatches[col] = {
                        "oracle": "<column_missing>",
                        "postgres": pval
                    }
                elif not values_equal(oval, pval):
                    row_mismatches[col] = {
                        "oracle": oval,
                        "postgres": pval
                    }
            
            if row_mismatches:
                mismatches_found = True
                report["mismatches_by_sourcenumber"][sn] = {
                    "mismatch_count": len(row_mismatches),
                    "columns": row_mismatches
                }
                
                # Console output (cleaner)
                print(f"\n🔴 Mismatch found for SOURCENUMBER: {sn}")
                for col, diff in row_mismatches.items():
                    print(f"   • {col:25} | Oracle: {diff['oracle']} | Postgres: {diff['postgres']}")

        if not mismatches_found and not missing_in_oracle and not missing_in_postgres:
            print(" ✅ No mismatch found.")

        # Save improved JSON
        with open(f"report_{table}.json", "w", encoding='utf-8') as f:
            json.dump(report, f, indent=2, default=str, ensure_ascii=False)
        
        print(f" 📄 Clean report saved to report_{table}.json")

    finally:
        ora_conn.close()
        pg_conn.close()


# ============================================================================
# Main
# ============================================================================
def main():
    print("🔁 Simple reconciliation started")
    print("🔁 Reconciliation started (no primary key, matches by SOURCENUMBER)")
    print(f"Source numbers: {SOURCE_NUMBERS}")
    for table in TABLES:
        try:
            reconcile_table(table, SOURCE_NUMBERS)
            reconcile_table(table)
        except Exception as e:
            print(f"  ❌ Error on {table}: {e}")
    print("\n✅ Done.")

if __name__ == "__main__":
    main()
