#!/usr/bin/env python3
"""
DISCOUNT Table Reconciliation (AlloyDB ↔ On-Prem)
Handles composite key (sourcenumber + ohlink) and multiple rows per source
"""

import os
import sys
import json
from datetime import datetime
from decimal import Decimal
import unicodedata
from contextlib import redirect_stdout

import oracledb
import psycopg2
from dotenv import load_dotenv

load_dotenv()

SOURCE_NUMBERS = [s.strip() for s in os.getenv("SOURCE_NUMBERS", "").split(",") if s.strip()]

if not SOURCE_NUMBERS:
    print("❌ No SOURCE_NUMBERS defined in .env")
    sys.exit(1)


# ========================== COLUMN MAPPING ==========================
COLUMN_MAPPING = {
    "SALESTRANID": ("SALESTRANID", "int8", "NUMBER"),
    "DISCOUNTID": ("SALESTRANDISCOUNTID", "int8", "NUMBER"),
    "SOURCENUMBER": ("SOURCENUMBER", "varchar(50)", "VARCHAR2(50)"),   # Will be derived
    "OHLINK": ("OHLINK", "varchar(100)", None),                        # Will be derived
    "SOURCEINSERTDATE": ("SOURCEINSERTDATE", "timestamp(0)", "DATE"),
    "SOURCEINSERTUSERID": ("SOURCEINSERTUSERID", "varchar(50)", "VARCHAR2(50)"),
    "SOURCESYSTEMID": ("SOURCESYSTEMID", "int4", "NUMBER"),
    "SOURCEUPDATEDATE": ("SOURCEUPDATEDATE", "timestamp(0)", "DATE"),
    "SOURCEUPDATEUSERID": ("SOURCEUPDATEUSERID", "varchar(50)", "VARCHAR2(50)"),
    "INSERTDATE": ("INSERTDATE", "timestamp(0)", "DATE"),
    "UPDATEDATE": ("UPDATEDATE", "timestamp(0)", "DATE"),
    "TRANDISCOUNTTYPE": ("TRANDISCOUNTTYPE", "varchar(50)", "VARCHAR2(50)"),
    "TRANDISCOUNTDESCRIPTION": ("TRANDISCOUNTDESCRIPTION", "varchar(100)", "VARCHAR2(50)"),
    "TRANDISCOUNTTOTALAMOUNT": ("TRANDISCOUNTTOTALAMOUNT", "numeric(19, 6)", "NUMBER(19,6)"),
}


# ========================== HELPERS ==========================
def normalize_value(val):
    if isinstance(val, str):
        return unicodedata.normalize('NFKC', val.strip())
    return val


def values_equal(a, b, alloy_type=None, onprem_type=None):
    if a is None and b is None:
        return True
    if a is None or b is None:
        return str(a).strip() == "" and str(b).strip() == ""

    a = normalize_value(a)
    b = normalize_value(b)

    try:
        if any(t and ('numeric' in str(t).lower() or t in ('int8','int4','NUMBER','decimal')) 
               for t in [alloy_type, onprem_type]):
            da = Decimal(str(a))
            db = Decimal(str(b))
            return abs(da - db) <= Decimal('0.01')

        elif any(t and ('time' in str(t).lower() or t == 'DATE') for t in [alloy_type, onprem_type]):
            if isinstance(a, datetime) and isinstance(b, datetime):
                return a.replace(microsecond=0) == b.replace(microsecond=0)
            return str(a)[:19] == str(b)[:19]

        else:
            return str(a).strip().lower() == str(b).strip().lower()
    except:
        return str(a).strip().lower() == str(b).strip().lower()


# ========================== FETCH FUNCTIONS ==========================
def fetch_oracle_discount_data(source_numbers):
    """Oracle - Uses transformation logic for sourcenumber and ohlink"""
    conn = oracledb.connect(
        user=os.getenv("ORACLE_USER"),
        password=os.getenv("ORACLE_PASSWORD"),
        dsn=os.getenv("ORACLE_DSN")
    )
    try:
        cur = conn.cursor()
        placeholders = ','.join([f"'{sn}'" for sn in source_numbers])
        
        sql = f"""
            SELECT 
                s.SALESTRANID,
                s.SALESTRANDISCOUNTID,
                SUBSTR(s.SOURCEHEADERKEY, 1, INSTR(s.SOURCEHEADERKEY, '.') - 1) AS SOURCENUMBER,
                SUBSTR(s.SOURCEHEADERKEY, INSTR(s.SOURCEHEADERKEY, '.') + 1) AS OHLINK,
                s.SOURCEINSERTDATE,
                s.SOURCEINSERTUSERID,
                s.SOURCESYSTEMID,
                s.SOURCEUPDATEDATE,
                s.SOURCEUPDATEUSERID,
                s.INSERTDATE,
                s.UPDATEDATE,
                s.TRANDISCOUNTTYPE,
                s.TRANDISCOUNTDESCRIPTION,
                s.TRANDISCOUNTTOTALAMOUNT
            FROM CEX01_OWN.SALESTRANDISCOUNT s
            WHERE SUBSTR(s.SOURCEHEADERKEY, 1, INSTR(s.SOURCEHEADERKEY, '.') - 1) IN ({placeholders})
        """
        cur.execute(sql)
        col_names = [desc[0].upper() for desc in cur.description]
        rows = cur.fetchall()
        cur.close()
        return col_names, rows
    finally:
        conn.close()


def fetch_postgres_discount_data(source_numbers):
    """AlloyDB - Direct fetch"""
    conn = psycopg2.connect(
        host=os.getenv("PG_HOST"),
        port=os.getenv("PG_PORT", "5432"),
        dbname=os.getenv("PG_DATABASE"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD")
    )
    try:
        cur = conn.cursor()
        placeholders = ','.join([f"'{sn}'" for sn in source_numbers])
        
        sql = f"""
            SELECT *
            FROM sba_own.discount
            WHERE sourcenumber IN ({placeholders})
        """
        cur.execute(sql)
        col_names = [desc[0].upper() for desc in cur.description]
        rows = cur.fetchall()
        cur.close()
        return col_names, rows
    finally:
        conn.close()


# ========================== MAIN RECONCILIATION ==========================
def reconcile_discount():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    txt_log = f"reconcile_discount_{timestamp}.txt"
    json_report = f"report_discount_{timestamp}.json"

    with open(txt_log, "w", encoding="utf-8") as f, redirect_stdout(f):
        print("DISCOUNT RECONCILIATION REPORT (AlloyDB ↔ On-Prem)")
        print(f"Run Time      : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Source Numbers: {SOURCE_NUMBERS}")
        print("=" * 140)

        try:
            # Fetch Data
            ora_cols, ora_rows = fetch_oracle_discount_data(SOURCE_NUMBERS)
            pg_cols, pg_rows = fetch_postgres_discount_data(SOURCE_NUMBERS)

            # Group by SOURCENUMBER (multiple rows possible)
            oracle_data = {}
            for row in ora_rows:
                sn = str(row[ora_cols.index("SOURCENUMBER")])
                oracle_data.setdefault(sn, []).append(dict(zip(ora_cols, row)))

            postgres_data = {}
            for row in pg_rows:
                sn = str(row[pg_cols.index("SOURCENUMBER")])
                postgres_data.setdefault(sn, []).append(dict(zip(pg_cols, row)))

            report = {
                "table": "DISCOUNT",
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
                o_rows = oracle_data[sn]
                p_rows = postgres_data[sn]

                print(f"\n📊 Processing SOURCENUMBER: {sn} | Oracle Rows: {len(o_rows)} | Postgres Rows: {len(p_rows)}")

                # Compare all combinations (multiple rows)
                for i, o_row in enumerate(o_rows):
                    for j, p_row in enumerate(p_rows):
                        mismatches = {}
                        renamed_comparisons = {}

                        for pg_col, (ora_col, alloy_type, onprem_type) in COLUMN_MAPPING.items():
                            if pg_col.upper() == "SOURCENUMBER":
                                continue

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

                        if mismatches:
                            key = f"{sn}_ora{i}_pg{j}"
                            report["mismatches_by_sourcenumber"][key] = {
                                "sourcenumber": sn,
                                "oracle_row": i,
                                "postgres_row": j,
                                "mismatch_count": len(mismatches),
                                "columns": mismatches
                            }
                            print(f"   🔴 MISMATCH (Oracle Row {i}, Postgres Row {j})")
                            for col, diff in mismatches.items():
                                print(f"     • {col:35} | AlloyDB: {diff['alloydb_value']} | On-Prem: {diff['onprem_value']} | {diff['onprem_type']}")

            # Summary
            print("\n" + "="*140)
            print("FINAL SUMMARY")
            print("="*140)
            print(f"Total Unique SOURCENUMBERs : {len(common_sns)}")
            print(f"Total Mismatches Found     : {len(report['mismatches_by_sourcenumber'])}")

            with open(json_report, "w", encoding='utf-8') as jf:
                json.dump(report, jf, indent=2, default=str, ensure_ascii=False)

            print(f"\n✅ Reconciliation Completed!")
            print(f"📝 Log  : {txt_log}")
            print(f"📊 JSON : {json_report}")

        except Exception as e:
            print(f"❌ Error: {e}")

    print(f"\n✅ Process finished. Check {txt_log}")


if __name__ == "__main__":
    reconcile_discount()