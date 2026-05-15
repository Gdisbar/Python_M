#!/usr/bin/env python3
"""
Specialized Reconciliation for SALESTRAN Table
AlloyDB ↔ On-Prem with Both-Side Data Type Awareness
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

# ========================== COMPLETE MAPPING WITH BOTH DATA TYPES ==========================
# Format: AlloyDB_Col: (OnPrem_Col, AlloyDB_Type, OnPrem_Type)
COLUMN_MAPPING = {
    "SALESTRANID": ("SALESTRANID", "int8", "NUMBER"),
    "ORDERTRANDATE": ("ORDERTRANDATE", "timestamp(0)", "DATE"),
    "SOURCEINSERTDATE": ("SOURCEINSERTDATE", "timestamp(0)", "DATE"),
    "SOURCESYSTEMID": ("SOURCESYSTEMID", "int4", "NUMBER"),
    "SOURCEUPDATEDATE": ("SOURCEUPDATEDATE", "timestamp(0)", "DATE"),
    "SOURCENUMBER": ("SOURCENUMBER", "varchar(50)", "VARCHAR2(50)"),
    "INSERTDATE": ("INSERTDATE", "timestamp(0)", "DATE"),
    "UPDATEDATE": ("UPDATEDATE", "timestamp(0)", "DATE"),
    "OHLINK": ("SOURCEHEADERID2", "varchar(100)", None),
    "SOURCEINSERTUSERID": ("SOURCEINSERTUSERID", "varchar(50)", "VARCHAR2(50)"),
    "SOURCEUPDATEUSERID": ("SOURCEUPDATEUSERID", "varchar(50)", "VARCHAR2(50)"),
    "OHCONO": ("SOURCEHEADERID3", "varchar(100)", None),
    "TRANTYPE": ("TRANTYPE", "varchar(50)", "VARCHAR2(50)"),
    "TRANMETHOD": ("TRANMETHOD", "varchar(50)", "VARCHAR2(50)"),
    "RECORDTYPE": ("RECORDTYPE", "varchar(50)", "VARCHAR2(50)"),
    "TRANAMOUNT": ("TRANAMOUNT", "numeric(19, 6)", "NUMBER(19,6)"),
    "DIVISIONCODE": ("DIVISIONCODE", "varchar(50)", "VARCHAR2(50)"),
    "CUSTOMERPONUMBER": ("CUSTOMERPONUMBER", "varchar(50)", "VARCHAR2(50)"),
    "BILLTOCOMPANY": ("BILLTOCOMPANY", "varchar(100)", "VARCHAR2(100)"),
    "BILLTOADDRESS1": ("BILLTOADDRESS1", "varchar(100)", "VARCHAR2(100)"),
    "BILLTOADDRESS2": ("BILLTOADDRESS2", "varchar(100)", "VARCHAR2(100)"),
    "BILLTOADDRESS3": ("BILLTOADDRESS3", "varchar(100)", "VARCHAR2(100)"),
    "BILLTOCITY": ("BILLTOCITY", "varchar(100)", "VARCHAR2(100)"),
    "BILLTOSTATE": ("BILLTOSTATE", "varchar(100)", "VARCHAR2(100)"),
    "BILLTOZIP": ("BILLTOZIP", "varchar(100)", "VARCHAR2(100)"),
    "BILLTOPHONE": ("BILLTOPHONE", "varchar(100)", "VARCHAR2(100)"),
    "BILLTOCOUNTRY": ("BILLTOCOUNTRY", "varchar(100)", "VARCHAR2(100)"),
    "SUPPLIER": ("SUPPLIER", "varchar(3)", "VARCHAR2(3)"),
    "SHIPTOFIRSTNAME": ("SHIPTOFIRSTNAME", "varchar(100)", "VARCHAR2(100)"),
    "SHIPTOLASTNAME": ("SHIPTOLASTNAME", "varchar(100)", "VARCHAR2(100)"),
    "SHIPTOCOMPANY": ("SHIPTOCOMPANY", "varchar(100)", "VARCHAR2(100)"),
    "SHIPTOADDRESS1": ("SHIPTOADDRESS1", "varchar(100)", "VARCHAR2(100)"),
    "SHIPTOADDRESS2": ("SHIPTOADDRESS2", "varchar(100)", "VARCHAR2(100)"),
    "SHIPTOADDRESS3": ("SHIPTOADDRESS3", "varchar(100)", "VARCHAR2(100)"),
    "SHIPTOCITY": ("SHIPTOCITY", "varchar(100)", "VARCHAR2(100)"),
    "SHIPTOSTATE": ("SHIPTOSTATE", "varchar(100)", "VARCHAR2(100)"),
    "SHIPTOZIP": ("SHIPTOZIP", "varchar(100)", "VARCHAR2(100)"),
    "SHIPTOCOUNTRY": ("SHIPTOCOUNTRY", "varchar(100)", "VARCHAR2(100)"),
    "SHIPTONUMBER": ("SHIPTONUMBER", "varchar(100)", "VARCHAR2(100)"),
    "SOURCESHIPTOID": ("SOURCESHIPTOID", "varchar(50)", "VARCHAR2(50)"),
    "PURCHASEORDERRELEASENAME": ("PURCHASEORDERRELEASENAME", "varchar(100)", "VARCHAR2(100)"),
    "ORDERERUSERID": ("ORDERERUSERID", "varchar(50)", "VARCHAR2(50)"),
    "ORDERERFIRSTNAME": ("ORDERERFIRSTNAME", "varchar(100)", "VARCHAR2(100)"),
    "ORDERERLASTNAME": ("ORDERERLASTNAME", "varchar(100)", "VARCHAR2(100)"),
    "ORDEREREMAILADDRESS": ("ORDEREREMAILADDRESS", "varchar(300)", "VARCHAR2(300)"),
    "ENTERPRISECODE": ("ENTERPRISECODE", "varchar(50)", "VARCHAR2(50)"),
    "MASTERNUMBER": ("MASTERNUMBER", "varchar(40)", "VARCHAR2(40)"),
    "BUDGETCENTERNAME": ("BUDGETCENTERNAME", "varchar(100)", "VARCHAR2(100)"),
    "LINELEVELBUDGET": ("LINELEVELBUDGET", "varchar(1)", "VARCHAR2(1)"),
    "TRANSTATUSNUMBER": ("TRANSTATUSNUMBER", "varchar(50)", "VARCHAR2(50)"),
    "SOURCEBILLTONUMBER": ("SOURCEBILLTONUMBER", "varchar(14)", "VARCHAR2(14)"),
    "SAVINGS_MEMBERSHIPTYPE": ("SAVINGS_MEMBERSHIPTYPE", "varchar(20)", "VARCHAR2(20)"),
    "SHIPTOSTATUS": ("SHIPTOSTATUS", "varchar(3)", "VARCHAR2(3)"),
    "ORDERERPHONENUMBER": ("ORDERERPHONENUMBER", "varchar(12)", "VARCHAR2(12)"),
    "SELLERSUBCODE": ("SELLERSUBCODE", "varchar(50)", "VARCHAR2(50)"),
    "SHIPTOPHONE": ("SHIPTOPHONE", "varchar(100)", "VARCHAR2(100)"),
    "BILLTO_ID": ("BILLTO_ID", "varchar(14)", "VARCHAR2(14)"),
    "FURNITURERECEIVERFNAME": ("FURNITURERECEIVERFNAME", "varchar(254)", "VARCHAR2(254)"),
    "FURNITURERECEIVERLNAME": ("FURNITURERECEIVERLNAME", "varchar(80)", "VARCHAR2(80)"),
    "FURNITURERECEIVEREMAIL": ("FURNITURERECEIVEREMAIL", "varchar(254)", "VARCHAR2(254)"),
    "FURNITURERECEIVERPHONE": ("FURNITURERECEIVERPHONE", "varchar(10)", "VARCHAR2(10)"),
    "ORDERSOURCE": ("ORDERSOURCE", "varchar(1)", "VARCHAR2(1)"),
    "HEADERLEVELSAVINGS": ("HEADERLEVELSAVINGS", "numeric(19, 6)", "NUMBER(19,6)"),
    "HEADERLEVELSAVINGSTYPECOD": ("HEADERLEVELSAVINGSTYPECOD", "varchar(50)", "VARCHAR2(50)"),
    "TOTALEARNEDSAVINGS": ("TOTALEARNEDSAVINGS", "numeric(19, 6)", "NUMBER(19,6)"),
}

# ========================== COMPARISON FUNCTION ==========================
def normalize_value(val):
    if isinstance(val, str):
        return unicodedata.normalize('NFKC', val.strip())
    return val

def values_equal(a, b, alloy_type=None, onprem_type=None):
    """Compare values considering both database types"""
    if a is None and b is None:
        return True
    if a is None or b is None:
        # Treat empty string as NULL
        if str(a).strip() == "" and str(b).strip() == "":
            return True
        return False

    a = normalize_value(a)
    b = normalize_value(b)

    try:
        # Numeric fields (most important for amounts)
        if any(t and 'numeric' in t.lower() or t in ('int8','int4','NUMBER','decimal') 
               for t in [alloy_type, onprem_type]):
            da = Decimal(str(a))
            db = Decimal(str(b))
            return abs(da - db) <= Decimal('0.01')

        # Date / Timestamp
        elif any(t and 'time' in t.lower() or t == 'DATE' for t in [alloy_type, onprem_type]):
            if isinstance(a, datetime) and isinstance(b, datetime):
                return a.replace(microsecond=0) == b.replace(microsecond=0)
            return str(a)[:19] == str(b)[:19]

        # String fields
        else:
            return str(a).strip().lower() == str(b).strip().lower()

    except Exception:
        return str(a).strip().lower() == str(b).strip().lower()


# ========================== CONNECTIONS ==========================
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


# ========================== MAIN ==========================
def reconcile_salestran():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    txt_log = f"reconcile_salestran_{timestamp}.txt"
    json_report = f"report_salestran_{timestamp}.json"

    with open(txt_log, "w", encoding="utf-8") as f, redirect_stdout(f):
        print("SALESTRAN RECONCILIATION REPORT (AlloyDB ↔ On-Prem)")
        print(f"Run Time      : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Source Numbers: {SOURCE_NUMBERS}")
        print("=" * 110)

        ora_conn = get_oracle_conn()
        pg_conn = get_postgres_conn()

        try:
            # Fetch Data
            cur = ora_conn.cursor()
            placeholders = ','.join([f"'{sn}'" for sn in SOURCE_NUMBERS])
            cur.execute(f"SELECT * FROM CEX01_OWN.SALESTRAN WHERE SOURCENUMBER IN ({placeholders})")
            ora_cols = [desc[0].upper() for desc in cur.description]
            ora_rows = cur.fetchall()
            cur.close()

            cur = pg_conn.cursor()
            cur.execute(f"SELECT * FROM sba_own.salestran WHERE sourcenumber IN ({placeholders})")
            pg_cols = [desc[0].upper() for desc in cur.description]
            pg_rows = cur.fetchall()
            cur.close()

            # Build dictionaries
            oracle_data = {}
            for row in ora_rows:
                sn = str(row[ora_cols.index("SOURCENUMBER")])
                oracle_data.setdefault(sn, []).append(dict(zip(ora_cols, row)))

            postgres_data = {}
            for row in pg_rows:
                sn = str(row[pg_cols.index("SOURCENUMBER")])
                postgres_data.setdefault(sn, []).append(dict(zip(pg_cols, row)))

            report = {
                "table": "SALESTRAN",
                "reconciled_on": datetime.now().isoformat(),
                "source_numbers": SOURCE_NUMBERS,
                "oracle_row_count": sum(len(v) for v in oracle_data.values()),
                "postgres_row_count": sum(len(v) for v in postgres_data.values()),
                "missing_in_oracle": list(set(postgres_data.keys()) - set(oracle_data.keys())),
                "missing_in_postgres": list(set(oracle_data.keys()) - set(postgres_data.keys())),
                "duplicates": {
                    "oracle": {k: len(v) for k, v in oracle_data.items() if len(v) > 1},
                    "postgres": {k: len(v) for k, v in postgres_data.items() if len(v) > 1}
                },
                "mismatches_by_sourcenumber": {}
            }

            common_sns = set(oracle_data.keys()) & set(postgres_data.keys())
            total_mismatches = 0

            for sn in sorted(common_sns):
                o_row = oracle_data[sn][0]
                p_row = postgres_data[sn][0]
                mismatches = {}

                for pg_col, (ora_col, alloy_type, onprem_type) in COLUMN_MAPPING.items():
                    if pg_col.upper() == "SOURCENUMBER":
                        continue

                    pg_val = p_row.get(pg_col.upper())
                    ora_val = o_row.get(ora_col) if ora_col else None

                    if not values_equal(pg_val, ora_val, alloy_type, onprem_type):
                        mismatches[pg_col] = {
                            "alloydb_value": pg_val,
                            "alloydb_type": alloy_type,
                            "onprem_value": ora_val,
                            "onprem_column": ora_col,
                            "onprem_type": onprem_type
                        }

                if mismatches:
                    total_mismatches += 1
                    report["mismatches_by_sourcenumber"][sn] = {
                        "mismatch_count": len(mismatches),
                        "columns": mismatches
                    }

                    print(f"\n🔴 MISMATCH → SOURCENUMBER: {sn}  ({len(mismatches)} differences)")
                    for col, diff in mismatches.items():
                        print(f"   • {col:40} | AlloyDB : {diff['alloydb_value']}  ({diff['alloydb_type']})")
                        print(f"   {'':40} | On-Prem : {diff['onprem_value']}  ({diff['onprem_column']}, {diff['onprem_type']})")

            # Summary
            print("\n" + "="*110)
            print("FINAL SUMMARY")
            print("="*110)
            print(f"Total SOURCENUMBERs Compared : {len(common_sns)}")
            print(f"Records with Mismatches      : {total_mismatches}")
            print(f"Missing in Oracle            : {len(report['missing_in_oracle'])}")
            print(f"Missing in On-Prem           : {len(report['missing_in_postgres'])}")

            with open(json_report, "w", encoding='utf-8') as jf:
                json.dump(report, jf, indent=2, default=str, ensure_ascii=False)

            print(f"\n✅ Done!")
            print(f"📝 Text Log    → {txt_log}")
            print(f"📊 JSON Report → {json_report}")

        finally:
            ora_conn.close()
            pg_conn.close()

    print(f"\n🎉 Process completed. Check {txt_log} for full details.")


if __name__ == "__main__":
    reconcile_salestran()
