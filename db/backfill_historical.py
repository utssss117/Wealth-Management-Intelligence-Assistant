# Backfills up to N days of historical NAV data using mfapi.in.
# Safe to re-run — INSERT OR IGNORE skips anything already in the DB.
# Run load_to_db.py first if the DB is fresh.
#
# Usage: python db/backfill_historical.py

import sqlite3
import os
import time
import requests
from datetime import date, timedelta, datetime


DB_PATH       = os.path.join("data", "nav.db")
LOOKBACK_DAYS = 90   # how far back to go on first run
REQUEST_DELAY = 0.5  # don't hammer the free API

MFAPI_BASE = "https://api.mfapi.in/mf"

# mfapi.in sometimes blocks plain Python requests; a browser UA fixes it
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
    )
}

# Funds to backfill — add/remove codes as needed,
# or call get_all_scheme_codes() to pull them straight from the DB.
SCHEME_CODES = [
    "100033",   # Aditya Birla SL Large & Mid Cap Fund - Regular - Growth
    "100034",   # Aditya Birla SL Large & Mid Cap Fund - Regular - IDCW
    "100037",   # Aditya Birla SL Income Fund - Regular - Qtrly IDCW
    "100038",   # Aditya Birla SL Income Fund - Regular - Growth
    "119598",   # Mirae Asset Large Cap Fund - Regular - Growth
    "120503",   # Axis Bluechip Fund - Regular - Growth
]


def fetch_nav_history(scheme_code: str) -> list[dict]:
    """Hit mfapi.in and return raw NAV records, or [] on any failure."""
    url = f"{MFAPI_BASE}/{scheme_code}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("status") != "SUCCESS":
            print(f"  [warn] non-SUCCESS status for {scheme_code}")
            return []
        return payload.get("data", [])
    except requests.exceptions.RequestException as e:
        print(f"  [error] {scheme_code}: {e}")
        return []
    except ValueError:
        print(f"  [error] bad JSON for {scheme_code}")
        return []


def parse_nav_date(date_str: str) -> str | None:
    """DD-MM-YYYY (API) -> YYYY-MM-DD (DB). Returns None on bad input."""
    try:
        return datetime.strptime(date_str, "%d-%m-%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def filter_to_lookback(records: list[dict], lookback_days: int) -> list[dict]:
    """Drop records older than lookback_days and reformat dates to YYYY-MM-DD."""
    cutoff = (date.today() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    result = []
    for rec in records:
        iso = parse_nav_date(rec["date"])
        if iso and iso >= cutoff:
            result.append({"date": iso, "nav": rec["nav"]})
    return result


def insert_nav_records(conn: sqlite3.Connection, scheme_code: str, records: list[dict]) -> int:
    """Insert records into nav_history. Returns count of actually-new rows."""
    cur = conn.cursor()
    inserted = 0
    for rec in records:
        try:
            nav = float(rec["nav"])
        except (ValueError, TypeError):
            continue  # skip rows with junk NAV values
        cur.execute(
            "INSERT OR IGNORE INTO nav_history (scheme_code, nav, nav_date) VALUES (?, ?, ?)",
            (scheme_code, nav, rec["date"]),
        )
        inserted += cur.rowcount  # 1 = new row, 0 = already existed
    conn.commit()
    return inserted


def check_scheme_exists(conn: sqlite3.Connection, scheme_code: str) -> bool:
    """Returns True if scheme_code is already in the schemes table."""
    return conn.execute(
        "SELECT 1 FROM schemes WHERE scheme_code = ?", (scheme_code,)
    ).fetchone() is not None


def main(scheme_codes: list[str] = SCHEME_CODES, lookback_days: int = LOOKBACK_DAYS) -> None:
    print(f"Backfilling last {lookback_days} days | {len(scheme_codes)} schemes | {DB_PATH}")
    print("-" * 60)

    conn = sqlite3.connect(DB_PATH)
    total = 0

    try:
        for code in scheme_codes:
            # nav_history has a FK on schemes, so skip unknown codes
            if not check_scheme_exists(conn, code):
                print(f"  [skip] {code} not in schemes table — run load_to_db.py first")
                continue

            print(f"  {code} ...", end=" ", flush=True)
            raw = fetch_nav_history(code)

            if not raw:
                print("no data")
                continue

            filtered = filter_to_lookback(raw, lookback_days)
            new_rows = insert_nav_records(conn, code, filtered)
            total += new_rows
            print(f"{len(filtered)} in window, {new_rows} new")

            time.sleep(REQUEST_DELAY)
    finally:
        conn.close()

    print("-" * 60)
    print(f"Done — {total} new rows total")


def get_all_scheme_codes(db_path: str = DB_PATH, limit: int = None) -> list[str]:
    """Pull every scheme code from the DB instead of using the hardcoded list.

    Example:
        main(scheme_codes=get_all_scheme_codes(limit=50))
    """
    conn = sqlite3.connect(db_path)
    sql = "SELECT scheme_code FROM schemes ORDER BY scheme_code"
    if limit:
        sql += f" LIMIT {limit}"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [r[0] for r in rows]
