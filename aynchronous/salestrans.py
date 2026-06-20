"""
salestran-SALESTRAN
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


# ========================== DATA FETCHING FUNCTIONS ==========================
def fetch_oracle_data(source_numbers):
    conn = oracledb.connect(
        user=os.getenv("ORACLE_USER"),
        password=os.getenv("ORACLE_PASSWORD"),
        dsn=os.getenv("ORACLE_DSN")
    )
    try:
        cur = conn.cursor()
        placeholders = ','.join([f"'{sn}'" for sn in source_numbers])
        sql = f"""
            SELECT * 
            FROM CEX01_OWN.SALESTRAN 
            WHERE SOURCENUMBER IN ({placeholders})
            -- Add extra filters here if needed in future
        """
        cur.execute(sql)
        col_names = [desc[0].upper() for desc in cur.description]
        rows = cur.fetchall()
        cur.close()
        return col_names, rows
    finally:
        conn.close()


def fetch_postgres_data(source_numbers):
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
            FROM sba_own.salestran 
            WHERE sourcenumber IN ({placeholders})
            -- Add extra filters here if needed in future
        """
        cur.execute(sql)
        col_names = [desc[0].upper() for desc in cur.description]
        rows = cur.fetchall()
        cur.close()
        return col_names, rows
    finally:
        conn.close()


# ========================== MAIN RECONCILIATION ==========================
def reconcile_salestran():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    txt_log = f"reconcile_salestran_{timestamp}.txt"
    json_report = f"report_salestran_{timestamp}.json"

    with open(txt_log, "w", encoding="utf-8") as f, redirect_stdout(f):
        print("SALESTRAN RECONCILIATION REPORT (AlloyDB ↔ On-Prem)")
        print(f"Run Time      : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Source Numbers: {SOURCE_NUMBERS}")
        print("=" * 130)

        try:
            # === Fetch Data 
            ora_cols, ora_rows = fetch_oracle_data(SOURCE_NUMBERS)
            pg_cols, pg_rows = fetch_postgres_data(SOURCE_NUMBERS)

            # Group by SOURCENUMBER (multiple rows)
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
                "mismatches_by_sourcenumber": {}
            }

            common_sns = set(oracle_data.keys()) & set(postgres_data.keys())

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
                    report["mismatches_by_sourcenumber"][sn] = {
                        "mismatch_count": len(mismatches),
                        "columns": mismatches
                    }
                    print(f"\n🔴 MISMATCH → SOURCENUMBER: {sn} ({len(mismatches)} differences)")
                    for col, diff in mismatches.items():
                        print(f" • {col:40} | AlloyDB : {diff['alloydb_value']}")
                        print(f" {'':40} | On-Prem : {diff['onprem_value']} ({diff['onprem_column']}) ({diff['onprem_type']})")

            # Summary
            print("\n" + "="*130)
            print("FINAL SUMMARY")
            print("="*130)
            print(f"Total SOURCENUMBERs Compared : {len(common_sns)}")
            print(f"SOURCENUMBERs with Mismatches: {len(report['mismatches_by_sourcenumber'])}")
            print(f"Missing in Oracle            : {len(report['missing_in_oracle'])}")
            print(f"Missing in On-Prem           : {len(report['missing_in_postgres'])}")

            with open(json_report, "w", encoding='utf-8') as jf:
                json.dump(report, jf, indent=2, default=str, ensure_ascii=False)

            print(f"\n✅ Reconciliation Completed!")
            print(f"📝 Log  : {txt_log}")
            print(f"📊 JSON : {json_report}")

        except Exception as e:
            print(f"❌ Error during reconciliation: {e}")

    print(f"\n✅ Process finished. Check {txt_log} for complete output.")


if __name__ == "__main__":
    reconcile_salestran()
