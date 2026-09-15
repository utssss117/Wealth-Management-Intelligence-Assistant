# End-to-end sanity check for the NAV pipeline.
# Usage: python test_pipeline.py

import os
import sys
import glob
import sqlite3

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from db.queries import get_nav_trend, compare_funds

RAW_FOLDER   = os.path.join("data", "raw")
CLEAN_FOLDER = os.path.join("data", "clean")
DB_PATH      = os.path.join("data", "nav.db")

AMFI_HEADER_FIELDS = ["Scheme Code", "Scheme Name", "Net Asset Value", "Date"]


def ok(msg: str):
    print(f"  [PASS] {msg}")

def fail(msg: str):
    print(f"  [FAIL] {msg}")

def section(title: str):
    print(f"\n{'-' * 60}\n  {title}\n{'-' * 60}")


def check_raw() -> tuple[bool, str]:
    section("Stage 1 - raw fetch  (data/raw/)")

    raw_files = sorted(glob.glob(os.path.join(RAW_FOLDER, "nav_raw_*.txt")))
    if not raw_files:
        fail("no nav_raw_*.txt files found in data/raw/")
        return False, "no raw files found"
    ok(f"found {len(raw_files)} raw file(s)")

    latest = max(raw_files, key=os.path.getmtime)
    size   = os.path.getsize(latest)
    print(f"  latest: {os.path.basename(latest)}  ({size:,} bytes)")

    if size == 0:
        fail("latest raw file is empty")
        return False, f"{os.path.basename(latest)} is empty"
    ok("file is non-empty")

    with open(latest, "r", encoding="utf-8", errors="replace") as f:
        first_line = next((l.strip() for l in f if l.strip()), "")

    print(f"  first line: {first_line[:120]}")

    if ";" not in first_line:
        fail("first line has no semicolons — doesn't look like AMFI format")
        return False, "raw file doesn't look like AMFI semicolon-delimited data"

    if not any(field in first_line for field in AMFI_HEADER_FIELDS):
        fail("first line doesn't contain expected AMFI header fields")
        return False, "raw file header doesn't match expected AMFI format"

    ok("file looks like real AMFI data")
    return True, ""


def check_clean() -> tuple[bool, str]:
    section("Stage 2 - clean CSV  (data/clean/)")

    csv_files = sorted(glob.glob(os.path.join(CLEAN_FOLDER, "nav_clean_*.csv")))
    if not csv_files:
        fail("no nav_clean_*.csv files found in data/clean/")
        return False, "no clean CSV files found"
    ok(f"found {len(csv_files)} clean file(s)")

    latest = max(csv_files, key=os.path.getmtime)
    print(f"  latest: {os.path.basename(latest)}")

    try:
        df = pd.read_csv(latest, dtype={"scheme_code": str})
    except Exception as e:
        fail(f"could not read CSV: {e}")
        return False, f"CSV read error: {e}"

    ok(f"loaded {len(df):,} rows, {len(df.columns)} columns")

    errors = []
    for col in ["scheme_code", "nav", "nav_date"]:
        if col not in df.columns:
            fail(f"column '{col}' is missing")
            errors.append(f"missing column: {col}")
            continue
        nulls = df[col].isnull().sum()
        if nulls > 0:
            fail(f"'{col}' has {nulls:,} nulls")
            errors.append(f"{col} has {nulls} nulls")
        else:
            ok(f"'{col}' — no nulls")

    # fund_house being empty was a bug we fixed — make sure it didn't regress
    if "fund_house" not in df.columns:
        fail("'fund_house' column is missing")
        errors.append("fund_house column missing")
    else:
        null_pct = df["fund_house"].isnull().mean() * 100
        if null_pct > 10:
            fail(f"'fund_house' is {null_pct:.1f}% null — old bug may be back")
            errors.append(f"fund_house is {null_pct:.1f}% null")
        else:
            ok(f"'fund_house' — {null_pct:.1f}% null")

    if errors:
        return False, "; ".join(errors)

    print(f"  distinct schemes: {df['scheme_code'].nunique():,}")
    print(f"  distinct fund houses: {df['fund_house'].nunique()}")
    return True, ""


def check_db() -> tuple[bool, str]:
    section("Stage 3 - database  (data/nav.db)")

    if not os.path.exists(DB_PATH):
        fail(f"{DB_PATH} does not exist")
        return False, "nav.db not found"

    try:
        conn = sqlite3.connect(DB_PATH)
    except Exception as e:
        fail(f"could not connect: {e}")
        return False, str(e)

    errors = []
    try:
        existing = {
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        for table in ["fund_houses", "schemes", "nav_history"]:
            if table in existing:
                ok(f"table '{table}' exists")
            else:
                fail(f"table '{table}' is MISSING")
                errors.append(f"missing table: {table}")

        if errors:
            return False, "; ".join(errors)

        print()
        for table in ["fund_houses", "schemes", "nav_history"]:
            n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table:<20} {n:>10,} rows")

        sample = conn.execute(
            "SELECT scheme_code FROM schemes ORDER BY RANDOM() LIMIT 1"
        ).fetchone()

        if not sample:
            fail("schemes table is empty")
            errors.append("schemes table empty")
        else:
            row = conn.execute(
                """
                SELECT fh.fund_house_name, nh.nav, nh.nav_date
                FROM   schemes     s
                JOIN   fund_houses fh ON s.fund_house_id = fh.fund_house_id
                JOIN   nav_history nh ON s.scheme_code   = nh.scheme_code
                WHERE  s.scheme_code = ?
                ORDER  BY nh.nav_date DESC LIMIT 1
                """,
                (sample[0],),
            ).fetchone()

            if not row or not row[0] or row[1] is None:
                fail(f"join for {sample[0]} returned nulls or nothing")
                errors.append("join produced nulls")
            else:
                ok(f"join OK — {sample[0]}: {row[0]}, NAV={row[1]}, date={row[2]}")

    finally:
        conn.close()

    if errors:
        return False, "; ".join(errors)
    return True, ""


def check_queries() -> tuple[bool, str]:
    section("Stage 4 - query functions  (db/queries.py)")

    errors = []

    try:
        conn = sqlite3.connect(DB_PATH)
        codes = [r[0] for r in conn.execute(
            "SELECT scheme_code FROM schemes ORDER BY RANDOM() LIMIT 3"
        ).fetchall()]
        min_date, max_date = conn.execute(
            "SELECT MIN(nav_date), MAX(nav_date) FROM nav_history"
        ).fetchone()
        conn.close()
    except Exception as e:
        fail(f"could not fetch test data from DB: {e}")
        return False, str(e)

    if not codes:
        fail("schemes table is empty")
        return False, "no scheme codes in DB"

    print(f"  using: {codes}  |  range: {min_date} -> {max_date}")

    print("\n  get_nav_trend:")
    trend = get_nav_trend(codes[0], min_date, max_date, db_path=DB_PATH)
    if isinstance(trend, dict):
        fail(f"get_nav_trend error: {trend['error']}")
        errors.append(f"get_nav_trend: {trend['error']}")
    else:
        ok(f"{len(trend)} rows for {codes[0]}")
        print(f"    first: {trend[0]}")
        print(f"    last:  {trend[-1]}")

    print("\n  compare_funds:")
    comparison = compare_funds(codes, db_path=DB_PATH)
    if isinstance(comparison, dict):
        fail(f"compare_funds error: {comparison['error']}")
        errors.append(f"compare_funds: {comparison['error']}")
    else:
        ok(f"{len(comparison)} scheme(s) returned")
        for code, name, house, nav, nav_date in comparison:
            if not house or nav is None:
                fail(f"row for {code} has nulls: fund_house={house!r}, nav={nav!r}")
                errors.append(f"compare_funds null in row for {code}")
            else:
                print(f"    [{code}] {name[:45]:<45} NAV={nav:<10} {nav_date}  [{house}]")

    if errors:
        return False, "; ".join(errors)
    return True, ""


def main():
    print("=" * 60)
    print("  NAV pipeline - end-to-end check")
    print("=" * 60)

    stages = [
        ("raw fetch",       check_raw),
        ("clean CSV",       check_clean),
        ("database",        check_db),
        ("query functions", check_queries),
    ]

    results = {}
    for name, fn in stages:
        try:
            passed, reason = fn()
        except Exception as e:
            passed, reason = False, f"unexpected exception: {e}"
        results[name] = (passed, reason)

    passed_count = sum(1 for p, _ in results.values() if p)
    print(f"\n{'=' * 60}\n  SUMMARY\n{'=' * 60}")
    print(f"  {passed_count}/{len(stages)} stages passed\n")

    for name, (passed, reason) in results.items():
        line = f"  [{'PASS' if passed else 'FAIL'}] {name}"
        if not passed:
            line += f"\n         >> {reason}"
        print(line)

    print()
    if passed_count < len(stages):
        sys.exit(1)


if __name__ == "__main__":
    main()

