# Query helpers for nav.db.
# Both functions return a list of tuples on success, or {"error": "..."} on failure.
# Dates should be "YYYY-MM-DD" strings — that's what nav_history stores.

import sqlite3


def get_nav_trend(
    scheme_code: str,
    start_date: str,
    end_date: str,
    db_path: str = "data/nav.db",
) -> list | dict:
    """NAV history for one scheme between two dates, oldest-first.

    Returns list of (nav_date, nav) tuples, or {"error": "..."} if nothing found.
    """
    sql = """
        SELECT nav_date, nav
        FROM   nav_history
        WHERE  scheme_code = ?
          AND  nav_date BETWEEN ? AND ?
        ORDER  BY nav_date ASC
    """
    try:
        conn = sqlite3.connect(db_path)
        try:
            rows = conn.execute(sql, (scheme_code, start_date, end_date)).fetchall()
        finally:
            conn.close()

        if not rows:
            return {"error": f"no data for {scheme_code!r} between {start_date} and {end_date}"}
        return rows

    except sqlite3.Error as e:
        return {"error": f"db error: {e}"}


def compare_funds(
    scheme_codes: list,
    db_path: str = "data/nav.db",
) -> list | dict:
    """Latest NAV + fund house name for each scheme code.

    Returns list of (scheme_code, scheme_name, fund_house_name, nav, nav_date),
    or {"error": "..."} if nothing matched.
    """
    if not scheme_codes:
        return {"error": "scheme_codes is empty"}

    placeholders = ", ".join("?" for _ in scheme_codes)

    sql = f"""
        SELECT
            s.scheme_code,
            s.scheme_name,
            fh.fund_house_name,
            nh.nav        AS latest_nav,
            nh.nav_date   AS latest_nav_date
        FROM   schemes     s
        JOIN   fund_houses fh ON s.fund_house_id = fh.fund_house_id
        JOIN   nav_history nh ON s.scheme_code   = nh.scheme_code
        WHERE  s.scheme_code IN ({placeholders})
          AND  nh.nav_date = (
                   SELECT MAX(nav_date)
                   FROM   nav_history
                   WHERE  scheme_code = s.scheme_code
               )
        ORDER  BY s.scheme_code
    """

    try:
        conn = sqlite3.connect(db_path)
        try:
            rows = conn.execute(sql, scheme_codes).fetchall()
        finally:
            conn.close()

        if not rows:
            return {"error": f"no data found for {scheme_codes!r}"}
        return rows

    except sqlite3.Error as e:
        return {"error": f"db error: {e}"}


# quick smoke test — run: python db/queries.py
if __name__ == "__main__":
    import os

    script_dir = os.path.dirname(os.path.abspath(__file__))
    DB = os.path.join(script_dir, "..", "data", "nav.db")

    TEST_CODES = ["100033", "100034", "100037"]

    print("--- get_nav_trend ---")
    result = get_nav_trend(TEST_CODES[0], "2026-06-01", "2026-09-12", db_path=DB)
    if isinstance(result, dict):
        print("error:", result["error"])
    else:
        print(f"{len(result)} rows for {TEST_CODES[0]}")
        print("  first:", result[0])
        print("  last: ", result[-1])

    print("\n--- compare_funds ---")
    result2 = compare_funds(TEST_CODES, db_path=DB)
    if isinstance(result2, dict):
        print("error:", result2["error"])
    else:
        for code, name, house, nav, nav_date in result2:
            print(f"  [{code}] {name[:50]:<50}  NAV={nav}  ({nav_date})  [{house}]")
