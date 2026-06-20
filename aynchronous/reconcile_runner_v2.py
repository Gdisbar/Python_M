# reconcile_runner.py
"""
Enterprise-grade Oracle ↔ Postgres Reconciliation Engine
=========================================================

Features
--------
* Row-level comparison with per-column type-aware normalisation
* Text (description) similarity scoring via difflib.SequenceMatcher
  — flags rows with high similarity but not exact match (whitespace,
    punctuation, unicode normalisation)
* Timestamp-aware comparison: strips microseconds, detects common
  timezone offsets (UTC vs IST etc.)
* Amount tolerance band with configurable threshold
* Row-hash fingerprinting for fast pre-screening (skip byte-identical rows)
* Missing-rows detection in both directions
* Rich console report (coloured terminal output)
* Machine-readable JSON export
* Summary statistics with mismatch-class breakdown
"""

import json
import copy
import hashlib
import unicodedata
import difflib
import re
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict


# ═══════════════════════════════════════════════════════════════════════════════
#  ANSI colour helpers
# ═══════════════════════════════════════════════════════════════════════════════

class C:
    RED    = "\033[91m"
    YELLOW = "\033[93m"
    GREEN  = "\033[92m"
    CYAN   = "\033[96m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    RESET  = "\033[0m"

def _c(color, text):
    return f"{color}{text}{C.RESET}"


# ═══════════════════════════════════════════════════════════════════════════════
#  Normalisation helpers
# ═══════════════════════════════════════════════════════════════════════════════

class Normalizer:
    """Type-aware value normalisation before comparison."""

    # Known timezone offsets that commonly cause drift between Oracle/Postgres
    _TZ_OFFSETS_SECONDS = [0, 3600, -3600, 19800, -19800, 7200, -7200]

    @staticmethod
    def normalize_string(value: Any) -> Optional[str]:
        if value is None:
            return None
        s = unicodedata.normalize("NFC", str(value))
        return s.strip().lower()

    @staticmethod
    def normalize_numeric(value: Any) -> Optional[Decimal]:
        if value is None:
            return None
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def normalize_timestamp(value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            # Strip microseconds — common JDBC / cx_Oracle precision artefact
            return value.replace(microsecond=0, tzinfo=None)
        # Attempt ISO string parse
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(str(value).strip(), fmt)
            except ValueError:
                pass
        return value

    @staticmethod
    def timestamp_tz_delta(a: datetime, b: datetime) -> Optional[int]:
        """
        If a and b differ by a known timezone offset (seconds), return that
        offset; else return None.
        """
        if a is None or b is None:
            return None
        diff = int((a - b).total_seconds())
        for offset in Normalizer._TZ_OFFSETS_SECONDS:
            if diff == offset:
                return offset
        return None

    @staticmethod
    def text_similarity(a: Optional[str], b: Optional[str]) -> float:
        """Return SequenceMatcher ratio in [0,1]."""
        if a is None and b is None:
            return 1.0
        if a is None or b is None:
            return 0.0
        return difflib.SequenceMatcher(None, a, b).ratio()

    @staticmethod
    def text_diff_details(a: Optional[str], b: Optional[str]) -> List[str]:
        """Return a compact list of unified-diff lines for text fields."""
        if a is None or b is None:
            return []
        diff = list(difflib.unified_diff(
            a.splitlines(), b.splitlines(),
            fromfile="oracle", tofile="postgres", lineterm=""
        ))
        return diff[:20]  # cap at 20 lines for readability


# ═══════════════════════════════════════════════════════════════════════════════
#  Row fingerprinting
# ═══════════════════════════════════════════════════════════════════════════════

def _row_hash(row: Tuple) -> str:
    """SHA-256 of canonical string representation — quick equality pre-screen."""
    canonical = "|".join(
        "" if v is None else
        Decimal(str(v)).quantize(Decimal("0.01")).__str__() if isinstance(v, (int, float, Decimal)) else
        str(v).strip().lower()
        for v in row
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════════
#  Mismatch data classes
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ColumnDiff:
    column: str
    oracle_value: Any
    postgres_value: Any
    mismatch_class: str          # e.g. "amount_drift", "case_mismatch", ...
    severity: str                # "CRITICAL" | "WARNING" | "INFO"
    detail: str = ""             # human-readable explanation
    similarity_score: Optional[float] = None   # for text columns
    text_diff: Optional[List[str]] = None      # unified diff lines


@dataclass
class RowMismatch:
    order_id: str
    column_diffs: List[ColumnDiff] = field(default_factory=list)

    @property
    def severity(self) -> str:
        """Worst severity across all column diffs."""
        for level in ("CRITICAL", "WARNING", "INFO"):
            if any(d.severity == level for d in self.column_diffs):
                return level
        return "INFO"


@dataclass
class ReconciliationResult:
    mismatches: List[RowMismatch] = field(default_factory=list)
    missing_in_postgres: List[str] = field(default_factory=list)
    missing_in_oracle: List[str] = field(default_factory=list)
    total_oracle_rows: int = 0
    total_postgres_rows: int = 0
    rows_skipped_identical: int = 0

    # ── Summary helpers ────────────────────────────────────────────────────────

    def mismatch_class_breakdown(self) -> Dict[str, int]:
        counts: Dict[str, int] = defaultdict(int)
        for rm in self.mismatches:
            for cd in rm.column_diffs:
                counts[cd.mismatch_class] += 1
        return dict(counts)

    def to_dict(self) -> dict:
        return {
            "summary": {
                "total_oracle_rows":       self.total_oracle_rows,
                "total_postgres_rows":     self.total_postgres_rows,
                "matched_rows":            (
                    self.total_oracle_rows
                    - len(self.mismatches)
                    - len(self.missing_in_postgres)
                ),
                "mismatched_rows":         len(self.mismatches),
                "missing_in_postgres":     len(self.missing_in_postgres),
                "missing_in_oracle":       len(self.missing_in_oracle),
                "rows_skipped_identical":  self.rows_skipped_identical,
                "mismatch_class_breakdown": self.mismatch_class_breakdown(),
            },
            "mismatches": [
                {
                    "order_id": rm.order_id,
                    "severity": rm.severity,
                    "column_diffs": [
                        {
                            "column":           cd.column,
                            "oracle_value":     str(cd.oracle_value),
                            "postgres_value":   str(cd.postgres_value),
                            "mismatch_class":   cd.mismatch_class,
                            "severity":         cd.severity,
                            "detail":           cd.detail,
                            "similarity_score": cd.similarity_score,
                            "text_diff":        cd.text_diff,
                        }
                        for cd in rm.column_diffs
                    ],
                }
                for rm in self.mismatches
            ],
            "missing_in_postgres": self.missing_in_postgres,
            "missing_in_oracle":   self.missing_in_oracle,
        }


# ═══════════════════════════════════════════════════════════════════════════════
#  Reconciliation engine
# ═══════════════════════════════════════════════════════════════════════════════

COLUMNS = ["order_id", "customer_name", "amount", "status", "description", "created_at"]

class ReconciliationEngine:
    """
    Compare Oracle and Postgres row sets and produce a detailed
    ReconciliationResult.

    Parameters
    ----------
    amount_tolerance : float
        Maximum allowed absolute difference for the amount column before
        flagging a mismatch.  Default 0.01 (1 cent).
    text_similarity_warn : float
        If description similarity is above this threshold but below 1.0,
        emit a WARNING instead of CRITICAL (near-match artefact).
    use_hash_prescreen : bool
        Skip byte-identical rows early using SHA-256 fingerprints.
    """

    def __init__(
        self,
        amount_tolerance: float = 0.01,
        text_similarity_warn: float = 0.90,
        use_hash_prescreen: bool = True,
    ):
        self.amount_tolerance = Decimal(str(amount_tolerance))
        self.text_similarity_warn = text_similarity_warn
        self.use_hash_prescreen = use_hash_prescreen

    # ── Public API ─────────────────────────────────────────────────────────────

    def compare(
        self,
        oracle_rows: List[Tuple],
        postgres_rows: List[Tuple],
    ) -> ReconciliationResult:

        result = ReconciliationResult(
            total_oracle_rows=len(oracle_rows),
            total_postgres_rows=len(postgres_rows),
        )

        pg_dict     = {row[0]: row for row in postgres_rows}
        oracle_dict = {row[0]: row for row in oracle_rows}

        # Oracle → Postgres pass
        for order_id, o_row in oracle_dict.items():
            if order_id not in pg_dict:
                result.missing_in_postgres.append(order_id)
                continue

            p_row = pg_dict[order_id]

            # Fast pre-screen
            if self.use_hash_prescreen and _row_hash(o_row) == _row_hash(p_row):
                result.rows_skipped_identical += 1
                continue

            diffs = self._compare_row(o_row, p_row)
            if diffs:
                result.mismatches.append(RowMismatch(order_id=order_id, column_diffs=diffs))
            else:
                result.rows_skipped_identical += 1

        # Reverse pass (ghost rows in Postgres)
        for order_id in pg_dict:
            if order_id not in oracle_dict:
                result.missing_in_oracle.append(order_id)

        # Sort mismatches: CRITICAL first, then WARNING, then INFO
        _sev_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
        result.mismatches.sort(key=lambda rm: _sev_order[rm.severity])

        return result

    # ── Per-row comparison ─────────────────────────────────────────────────────

    def _compare_row(self, o: Tuple, p: Tuple) -> List[ColumnDiff]:
        diffs: List[ColumnDiff] = []

        for idx, col in enumerate(COLUMNS):
            o_val = o[idx]
            p_val = p[idx]
            cd = self._compare_column(col, o_val, p_val)
            if cd:
                diffs.append(cd)

        return diffs

    def _compare_column(self, col: str, o_val: Any, p_val: Any) -> Optional[ColumnDiff]:

        # ── amount ──────────────────────────────────────────────────────────────
        if col == "amount":
            o_n = Normalizer.normalize_numeric(o_val)
            p_n = Normalizer.normalize_numeric(p_val)
            if o_n is None and p_n is None:
                return None
            if o_n is None or p_n is None:
                return ColumnDiff(col, o_val, p_val, "null_mismatch", "CRITICAL",
                                  "One side is NULL")
            delta = abs(o_n - p_n)
            if delta == 0:
                return None
            if delta <= self.amount_tolerance:
                return ColumnDiff(col, o_n, p_n, "amount_rounding_noise", "INFO",
                                  f"Δ={delta} within tolerance {self.amount_tolerance}")
            severity = "CRITICAL" if delta > Decimal("1.00") else "WARNING"
            return ColumnDiff(col, o_n, p_n, "amount_drift", severity,
                              f"Δ={delta} exceeds tolerance {self.amount_tolerance}")

        # ── created_at ──────────────────────────────────────────────────────────
        elif col == "created_at":
            o_n = Normalizer.normalize_timestamp(o_val)
            p_n = Normalizer.normalize_timestamp(p_val)
            if o_n == p_n:
                return None
            tz_delta = Normalizer.timestamp_tz_delta(
                o_val if isinstance(o_val, datetime) else o_n,
                p_val if isinstance(p_val, datetime) else p_n,
            )
            if tz_delta is not None:
                h = tz_delta // 3600
                return ColumnDiff(col, o_n, p_n, "timezone_shift", "WARNING",
                                  f"Offset matches known TZ drift ({h:+d}h)")
            # Check if raw values (with microseconds) differ but normalised match
            raw_o = o_val.replace(tzinfo=None) if isinstance(o_val, datetime) else o_val
            raw_p = p_val.replace(tzinfo=None) if isinstance(p_val, datetime) else p_val
            if isinstance(raw_o, datetime) and isinstance(raw_p, datetime):
                if raw_o.replace(microsecond=0) == raw_p.replace(microsecond=0):
                    return ColumnDiff(col, raw_o, raw_p,
                                      "timestamp_microsecond_precision", "INFO",
                                      "Differ only in sub-second precision")
            return ColumnDiff(col, o_n, p_n, "timestamp_mismatch", "CRITICAL",
                              f"Oracle={o_n!s}  Postgres={p_n!s}")

        # ── description (rich text comparison) ──────────────────────────────────
        elif col == "description":
            o_raw = str(o_val).strip() if o_val is not None else None
            p_raw = str(p_val).strip() if p_val is not None else None

            if o_raw == p_raw:
                return None

            o_n = Normalizer.normalize_string(o_val)
            p_n = Normalizer.normalize_string(p_val)

            sim = Normalizer.text_similarity(o_n, p_n)
            diff_lines = Normalizer.text_diff_details(o_raw, p_raw)

            if o_n == p_n:
                # Identical after normalisation → whitespace / case artefact
                return ColumnDiff(col, o_raw, p_raw,
                                  "description_whitespace_case", "INFO",
                                  "Identical after strip+lowercase",
                                  similarity_score=sim)

            if sim >= self.text_similarity_warn:
                severity = "WARNING"
                mclass = "description_near_match"
                detail = f"High similarity ({sim:.1%}) — possible ETL artefact"
            else:
                severity = "CRITICAL"
                mclass = "description_content_mismatch"
                detail = f"Low similarity ({sim:.1%}) — content changed"

            return ColumnDiff(col, o_raw, p_raw, mclass, severity,
                              detail, similarity_score=round(sim, 4),
                              text_diff=diff_lines)

        # ── string columns (order_id, customer_name, status) ────────────────────
        else:
            o_n = Normalizer.normalize_string(o_val)
            p_n = Normalizer.normalize_string(p_val)

            if o_n == p_n:
                return None

            # Check whether difference is purely case
            if (o_n or "").lower() == (p_n or "").lower():
                return ColumnDiff(col, o_val, p_val, "case_mismatch", "INFO",
                                  f"Values identical ignoring case: '{o_val}' vs '{p_val}'")

            return ColumnDiff(col, o_val, p_val, "value_mismatch", "CRITICAL",
                              f"'{o_val}' ≠ '{p_val}'")


# ═══════════════════════════════════════════════════════════════════════════════
#  Console reporter
# ═══════════════════════════════════════════════════════════════════════════════

SEV_COLOUR = {
    "CRITICAL": C.RED,
    "WARNING":  C.YELLOW,
    "INFO":     C.CYAN,
}

def print_report(result: ReconciliationResult, max_rows: int = 20):
    """Pretty-print a reconciliation result to the terminal."""

    s = result.to_dict()["summary"]
    print()
    print(_c(C.BOLD, "═" * 70))
    print(_c(C.BOLD, "  RECONCILIATION REPORT"))
    print(_c(C.BOLD, "═" * 70))
    print(f"  Oracle rows      : {s['total_oracle_rows']}")
    print(f"  Postgres rows    : {s['total_postgres_rows']}")
    print(f"  Matched (clean)  : {_c(C.GREEN,  str(s['matched_rows']))}")
    print(f"  Mismatched rows  : {_c(C.RED,    str(s['mismatched_rows']))}")
    print(f"  Missing in PG    : {_c(C.YELLOW, str(s['missing_in_postgres']))}")
    print(f"  Missing in Oracle: {_c(C.YELLOW, str(s['missing_in_oracle']))}")
    print(f"  Skipped (hash=)  : {_c(C.DIM,   str(s['rows_skipped_identical']))}")

    if s["mismatch_class_breakdown"]:
        print()
        print(_c(C.BOLD, "  Mismatch class breakdown:"))
        for cls, cnt in sorted(s["mismatch_class_breakdown"].items(),
                               key=lambda x: -x[1]):
            print(f"    {cls:<45} {cnt:>4}")

    # ── Missing rows ───────────────────────────────────────────────────────────
    if result.missing_in_postgres:
        print()
        print(_c(C.YELLOW, f"  ⚠  Rows present in Oracle but MISSING in Postgres ({len(result.missing_in_postgres)}):"))
        for oid in result.missing_in_postgres[:10]:
            print(f"     • {oid}")
        if len(result.missing_in_postgres) > 10:
            print(f"     … and {len(result.missing_in_postgres)-10} more")

    if result.missing_in_oracle:
        print()
        print(_c(C.YELLOW, f"  ⚠  Rows present in Postgres but MISSING in Oracle ({len(result.missing_in_oracle)}):"))
        for oid in result.missing_in_oracle[:10]:
            print(f"     • {oid}")

    # ── Row mismatches ─────────────────────────────────────────────────────────
    if result.mismatches:
        print()
        print(_c(C.BOLD, f"  Row-level mismatches (showing up to {max_rows}):"))
        print(_c(C.BOLD, "  " + "─" * 66))

        for rm in result.mismatches[:max_rows]:
            sev_col = SEV_COLOUR.get(rm.severity, C.RESET)
            print()
            print(f"  {_c(sev_col, f'[{rm.severity}]')} Order: {_c(C.BOLD, rm.order_id)}")
            for cd in rm.column_diffs:
                cc = SEV_COLOUR.get(cd.severity, C.RESET)
                print(f"    {_c(cc, '●')} Column: {cd.column:<18} class: {cd.mismatch_class}")
                print(f"      Oracle  : {str(cd.oracle_value)[:80]}")
                print(f"      Postgres: {str(cd.postgres_value)[:80]}")
                if cd.detail:
                    print(f"      Detail  : {_c(C.DIM, cd.detail)}")
                if cd.similarity_score is not None:
                    bar_len = int(cd.similarity_score * 20)
                    bar = "█" * bar_len + "░" * (20 - bar_len)
                    print(f"      Similarity: [{bar}] {cd.similarity_score:.1%}")
                if cd.text_diff:
                    print(f"      Diff (unified):")
                    for line in cd.text_diff[:6]:
                        clr = C.GREEN if line.startswith("+") else C.RED if line.startswith("-") else C.DIM
                        print(f"        {_c(clr, line)}")

        if len(result.mismatches) > max_rows:
            print()
            print(_c(C.DIM, f"  … {len(result.mismatches) - max_rows} more mismatched rows — see JSON export."))

    print()
    print(_c(C.BOLD, "═" * 70))
    print()


# ═══════════════════════════════════════════════════════════════════════════════
#  DB client imports — kept thin so the engine is testable without live DBs
# ═══════════════════════════════════════════════════════════════════════════════

def _try_import_clients():
    """Lazy import so the module loads even without oracledb / psycopg2."""
    try:
        from oracle_client import OracleClient
    except ImportError:
        OracleClient = None
    try:
        from postgres_client import PostgresClient
    except ImportError:
        PostgresClient = None
    return OracleClient, PostgresClient


# ═══════════════════════════════════════════════════════════════════════════════
#  Demo / test runner (no live DB required)
# ═══════════════════════════════════════════════════════════════════════════════

def run_demo():
    """
    Runs a self-contained demo using generated in-memory data.
    Simulates what would happen when rows are fetched from live databases.
    """
    from data_generator_v2 import DataGenerator

    print(_c(C.BOLD + C.CYAN, "\n  Generating demo data …"))
    base = DataGenerator.generate_orders(200)

    oracle_data  = copy.deepcopy(base)
    pg_data_raw  = copy.deepcopy(base)

    # Inject field-level mismatches into Postgres copy
    pg_mutated, field_report = DataGenerator.introduce_mismatch(pg_data_raw, seed=42)

    # Inject missing/ghost rows
    pg_final, row_report = DataGenerator.introduce_missing_rows(
        oracle_data, pg_mutated, missing_pct=0.03
    )

    print(f"  Oracle rows      : {len(oracle_data)}")
    print(f"  Postgres rows    : {len(pg_final)}")
    print(f"  Injected field ∆ : {len(field_report)}")
    print(f"  Missing in PG    : {len(row_report['missing_in_target'])}")
    print(f"  Ghost in PG      : {len(row_report['extra_in_target'])}")

    # Convert dicts → tuples (as DB drivers return)
    def _to_tuples(data):
        return [
            (
                r["order_id"],
                r["customer_name"],
                r["amount"],
                r["status"],
                r["description"],
                r["created_at"],
            )
            for r in data
        ]

    oracle_rows   = _to_tuples(oracle_data)
    postgres_rows = _to_tuples(pg_final)

    engine = ReconciliationEngine(
        amount_tolerance=0.01,
        text_similarity_warn=0.92,
        use_hash_prescreen=True,
    )

    result = engine.compare(oracle_rows, postgres_rows)
    print_report(result, max_rows=30)

    # Export JSON
    out_path = "reconciliation_report.json"
    with open(out_path, "w") as fh:
        json.dump(result.to_dict(), fh, indent=2, default=str)
    print(f"  JSON report written to: {out_path}\n")

    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  Live DB runner
# ═══════════════════════════════════════════════════════════════════════════════

def run_live(
    oracle_cfg: dict,
    postgres_cfg: dict,
    amount_tolerance: float = 0.01,
    text_similarity_warn: float = 0.92,
):
    """
    Connect to real Oracle (ExaDB) and Postgres (AlloyDB / CloudSQL), fetch
    all rows from the orders table, and reconcile.

    oracle_cfg  : dict with keys user, password, dsn
    postgres_cfg: dict with keys host, db, user, password
    """
    OracleClient, PostgresClient = _try_import_clients()

    if OracleClient is None or PostgresClient is None:
        raise ImportError("oracledb and psycopg2 must be installed for live mode.")

    print("  Connecting to Oracle …")
    oracle = OracleClient(**oracle_cfg)

    print("  Connecting to Postgres …")
    postgres = PostgresClient(**postgres_cfg)

    print("  Fetching Oracle rows …")
    oracle_rows = oracle.fetch_all()

    print("  Fetching Postgres rows …")
    postgres_rows = postgres.fetch_all()

    engine = ReconciliationEngine(
        amount_tolerance=amount_tolerance,
        text_similarity_warn=text_similarity_warn,
    )
    result = engine.compare(oracle_rows, postgres_rows)
    print_report(result)

    out_path = "reconciliation_report.json"
    with open(out_path, "w") as fh:
        json.dump(result.to_dict(), fh, indent=2, default=str)
    print(f"  JSON report written to: {out_path}\n")

    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "demo"

    if mode == "demo":
        run_demo()

    elif mode == "live":
        # Example:  python reconcile_runner.py live
        # Adjust credentials below or load from env / config file
        import os
        run_live(
            oracle_cfg={
                "user":     os.getenv("ORACLE_USER", "app_user"),
                "password": os.getenv("ORACLE_PASSWORD", "AppUserPass123"),
                "dsn":      os.getenv("ORACLE_DSN", "localhost:1521/XEPDB1"),
            },
            postgres_cfg={
                "host":     os.getenv("PG_HOST", "localhost"),
                "db":       os.getenv("PG_DB",   "xepdb2"),
                "user":     os.getenv("PG_USER",  "app_user"),
                "password": os.getenv("PG_PASSWORD", "AppUserPass123"),
            },
        )
    else:
        print(f"Unknown mode '{mode}'. Use 'demo' or 'live'.")
        sys.exit(1)