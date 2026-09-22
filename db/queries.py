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
    scheme_codes: list | str,
    db_path: str = "data/nav.db",
) -> list | dict:
    """Latest NAV + fund house name for each scheme code.

    Returns list of (scheme_code, scheme_name, fund_house_name, nav, nav_date),
    or {"error": "..."} if nothing matched.

    scheme_codes may be a list of code strings OR a comma-separated string —
    both are handled. If a string arrives, it is coerced to a list and a
    warning is printed so callers can see the type mismatch in their logs.
    """
    # ── Defensive coercion: agent @tool passes a comma-separated string ──────
    if isinstance(scheme_codes, str):
        print(
            f"[compare_funds WARNING] received a string {scheme_codes!r} "
            f"instead of a list — coercing by splitting on commas. "
            f"Fix the caller to pass a list for cleanliness."
        )
        scheme_codes = [c.strip() for c in scheme_codes.split(",") if c.strip()]
    # ─────────────────────────────────────────────────────────────────────────

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



def find_scheme_by_name(
    name_query: str,
    db_path: str = "data/nav.db",
) -> list | dict:
    """Case-insensitive partial match on scheme_name.

    Returns list of (scheme_code, scheme_name, fund_house_name) tuples,
    or {"error": "..."} if nothing matched.
    """
    sql = """
        SELECT s.scheme_code, s.scheme_name, fh.fund_house_name
        FROM   schemes     s
        JOIN   fund_houses fh ON s.fund_house_id = fh.fund_house_id
        WHERE  LOWER(s.scheme_name) LIKE LOWER(?)
        ORDER  BY s.scheme_name
    """
    try:
        conn = sqlite3.connect(db_path)
        try:
            rows = conn.execute(sql, (f"%{name_query}%",)).fetchall()
        finally:
            conn.close()

        if not rows:
            return {"error": f"no schemes matching {name_query!r}"}
        return rows

    except sqlite3.Error as e:
        return {"error": f"db error: {e}"}



