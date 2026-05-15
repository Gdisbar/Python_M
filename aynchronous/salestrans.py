#!/usr/bin/env python3
"""
Specialized Reconciliation for SALESTRAN Table
AlloyDB (Postgres) ↔ On-Prem (Oracle)
Console output + JSON report + TXT log
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
    "SALESTRANID": "SALESTRANID",
    "ORDERTRANDATE": "ORDERTRANDATE",
    "SOURCEINSERTDATE": "SOURCEINSERTDATE",
    "SOURCESYSTEMID": "SOURCESYSTEMID",
    "SOURCEUPDATEDATE": "SOURCEUPDATEDATE",
    "SOURCENUMBER": "SOURCENUMBER",
    "INSERTDATE": "INSERTDATE",
    "UPDATEDATE": "UPDATEDATE",
    "OHLINK": "SOURCEHEADERID2",
    "SOURCEINSERTUSERID": "SOURCEINSERTUSERID",
    "SOURCEUPDATEUSERID": "SOURCEUPDATEUSERID",
    "OHCONO": "SOURCEHEADERID3",
    "TRANTYPE": "TRANTYPE",
    "TRANMETHOD": "TRANMETHOD",
    "RECORDTYPE": "RECORDTYPE",
    "TRANAMOUNT": "TRANAMOUNT",
    "DIVISIONCODE": "DIVISIONCODE",
    "CUSTOMERPONUMBER": "CUSTOMERPONUMBER",
    "BILLTOCOMPANY": "BILLTOCOMPANY",
    "BILLTOADDRESS1": "BILLTOADDRESS1",
    "BILLTOADDRESS2": "BILLTOADDRESS2",
    "BILLTOADDRESS3": "BILLTOADDRESS3",
    "BILLTOCITY": "BILLTOCITY",
    "BILLTOSTATE": "BILLTOSTATE",
    "BILLTOZIP": "BILLTOZIP",
    "BILLTOPHONE": "BILLTOPHONE",
    "BILLTOCOUNTRY": "BILLTOCOUNTRY",
    "SUPPLIER": "SUPPLIER",
    "SHIPTOFIRSTNAME": "SHIPTOFIRSTNAME",
    "SHIPTOLASTNAME": "SHIPTOLASTNAME",
    "SHIPTOCOMPANY": "SHIPTOCOMPANY",
    "SHIPTOADDRESS1": "SHIPTOADDRESS1",
    "SHIPTOADDRESS2": "SHIPTOADDRESS2",
    "SHIPTOADDRESS3": "SHIPTOADDRESS3",
    "SHIPTOCITY": "SHIPTOCITY",
    "SHIPTOSTATE": "SHIPTOSTATE",
    "SHIPTOZIP": "SHIPTOZIP",
    "SHIPTOCOUNTRY": "SHIPTOCOUNTRY",
    "SHIPTONUMBER": "SHIPTONUMBER",
    "SOURCESHIPTOID": "SOURCESHIPTOID",
    "PURCHASEORDERRELEASENAME": "PURCHASEORDERRELEASENAME",
    "ORDERERUSERID": "ORDERERUSERID",
    "ORDERERFIRSTNAME": "ORDERERFIRSTNAME",
    "ORDERERLASTNAME": "ORDERERLASTNAME",
    "ORDEREREMAILADDRESS": "ORDEREREMAILADDRESS",
    "ENTERPRISECODE": "ENTERPRISECODE",
    "MASTERNUMBER": "MASTERNUMBER",
    "BUDGETCENTERNAME": "BUDGETCENTERNAME",
    "LINELEVELBUDGET": "LINELEVELBUDGET",
    "TRANSTATUSNUMBER": "TRANSTATUSNUMBER",
    "SOURCEBILLTONUMBER": "SOURCEBILLTONUMBER",
    "SAVINGS_MEMBERSHIPTYPE": "SAVINGS_MEMBERSHIPTYPE",
    "SHIPTOSTATUS": "SHIPTOSTATUS",
    "ORDERERPHONENUMBER": "ORDERERPHONUMBER",
    "SELLERSUBCODE": "SELLERSUBCODE",
    "SHIPTOPHONE": "SHIPTOPHONE",
    "BILLTO_ID": "BILLTO_ID",
    "FURNITURERECEIVERFNAME": "FURNITURERECEIVERFNAME",
    "FURNITURERECEIVERLNAME": "FURNITURERECEIVERLNAME",
    "FURNITURERECEIVEREMAIL": "FURNITURERECEIVEREMAIL",
    "FURNITURERECEIVERPHONE": "FURNITURERECEIVERPHONE",
    "ORDERSOURCE": "ORDERSOURCE",
    "HEADERLEVELSAVINGS": "HEADERLEVELSAVINGS",
    "HEADERLEVELSAVINGSTYPECOD": "HEADERLEVELSAVINGSTYPECOD",
    "TOTALEARNEDSAVINGS": "TOTALEARNEDSAVINGS",
}

# ========================== HELPERS ==========================
def normalize_value(val):
    if isinstance(val, str):
        return unicodedata.normalize('NFKC', val.strip())
    return val

def values_equal(a, b):
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False

    a = normalize_value(a)
    b = normalize_value(b)

    if isinstance(a, (int, float, Decimal)) and isinstance(b, (int, float, Decimal)):
        try:
            return abs(Decimal(str(a)) - Decimal(str(b))) < Decimal('0.0001')
        except:
            return False

    if isinstance(a, datetime) and isinstance(b, datetime):
        return a.replace(tzinfo=None) == b.replace(tzinfo=None)

    return str(a).lower() == str(b).lower()


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


# ========================== MAIN FUNCTION ==========================
def reconcile_salestran():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    txt_log = f"reconcile_salestran_{timestamp}.txt"
    json_report = f"report_salestran_{timestamp}.json"

    # Redirect console output to both terminal + file
    with open(txt_log, "w", encoding="utf-8") as f, redirect_stdout(f):
        print(f"RECONCILIATION REPORT - SALESTRAN")
        print(f"Run Date     : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Source Numbers: {SOURCE_NUMBERS}")
        print("="*90)

        ora_conn = get_oracle_conn()
        pg_conn = get_postgres_conn()

        try:
            # Fetch Oracle
            cur = ora_conn.cursor()
            placeholders = ','.join([f"'{sn}'" for sn in SOURCE_NUMBERS])
            cur.execute(f"SELECT * FROM CEX01_OWN.SALESTRAN WHERE SOURCENUMBER IN ({placeholders})")
            ora_cols = [desc[0].upper() for desc in cur.description]
            ora_rows = cur.fetchall()
            cur.close()

            # Fetch Postgres (AlloyDB)
            cur = pg_conn.cursor()
            cur.execute(f"SELECT * FROM sba_own.salestran WHERE sourcenumber IN ({placeholders})")
            pg_cols = [desc[0].upper() for desc in cur.description]
            pg_rows = cur.fetchall()
            cur.close()

            # Group by SOURCENUMBER
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

                for pg_col, ora_col in COLUMN_MAPPING.items():
                    if pg_col.upper() == "SOURCENUMBER":
                        continue
                    pg_val = p_row.get(pg_col.upper())
                    ora_val = o_row.get(ora_col.upper() if ora_col else None)

                    if not values_equal(pg_val, ora_val):
                        mismatches[pg_col] = {
                            "alloydb_value": pg_val,
                            "onprem_value": ora_val,
                            "onprem_column": ora_col
                        }

                if mismatches:
                    total_mismatches += 1
                    report["mismatches_by_sourcenumber"][sn] = {
                        "mismatch_count": len(mismatches),
                        "columns": mismatches
                    }

                    print(f"\n🔴 MISMATCH → SOURCENUMBER: {sn}  ({len(mismatches)} differences)")
                    for col, diff in mismatches.items():
                        print(f"   • {col:40} | AlloyDB : {diff['alloydb_value']}")
                        print(f"   {'':40} | On-Prem : {diff['onprem_value']}  ({diff['onprem_column']})")

            # Summary
            print("\n" + "="*90)
            print("SUMMARY")
            print("="*90)
            print(f"Total SOURCENUMBER processed : {len(common_sns)}")
            print(f"Total mismatches found       : {total_mismatches}")
            print(f"Missing in Oracle            : {len(report['missing_in_oracle'])}")
            print(f"Missing in On-Prem           : {len(report['missing_in_postgres'])}")

            # Save JSON Report
            with open(json_report, "w", encoding='utf-8') as jf:
                json.dump(report, jf, indent=2, default=str, ensure_ascii=False)

            print(f"\n✅ Reconciliation Completed!")
            print(f"📄 JSON Report : {json_report}")
            print(f"📝 Text Log    : {txt_log}")

        finally:
            ora_conn.close()
            pg_conn.close()

    # Also print final message to console
    print(f"\n🎉 Done! Reports generated:")
    print(f"   • {txt_log}  (Readable console output)")
    print(f"   • {json_report} (Structured data)")


if __name__ == "__main__":
    reconcile_salestran()