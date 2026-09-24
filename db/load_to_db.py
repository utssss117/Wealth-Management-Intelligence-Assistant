import sqlite3
import os
import glob
import pandas as pd


DB_PATH      = os.path.join("data", "nav.db")
SCHEMA_PATH  = os.path.join("db", "schema.sql")
CLEAN_FOLDER = os.path.join("data", "clean")


def get_latest_csv(folder: str) -> str:
    csv_files = glob.glob(os.path.join(folder, "*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files in '{folder}' — did the cleaning step run?")
    return max(csv_files, key=os.path.getmtime)


def setup_db(conn: sqlite3.Connection) -> None:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"scheme_code": str})
    df["nav_date"] = pd.to_datetime(df["nav_date"]).dt.strftime("%Y-%m-%d")
    return df


def insert_data(conn: sqlite3.Connection, df: pd.DataFrame) -> None:
    cur = conn.cursor()
    house_id_cache: dict[str, int] = {}

    for _, row in df.iterrows():
        house   = row["fund_house"]
        code    = row["scheme_code"]
        nav     = float(row["nav"])
        date    = row["nav_date"]
        isin_g  = row["isin_growth"]
        isin_r  = row["isin_reinvest"]
        name    = row["scheme_name"]

        if house not in house_id_cache:
            cur.execute("INSERT OR IGNORE INTO fund_houses (fund_house_name) VALUES (?)", (house,))
            cur.execute("SELECT fund_house_id FROM fund_houses WHERE fund_house_name = ?", (house,))
            house_id_cache[house] = cur.fetchone()[0]

        house_id = house_id_cache[house]

        cur.execute(
            (code, house_id, isin_g, isin_r, name),
        )
        cur.execute(
            "INSERT OR IGNORE INTO nav_history (scheme_code, nav, nav_date) VALUES (?, ?, ?)",
            (code, nav, date),
        )

    conn.commit()


def print_counts(conn: sqlite3.Connection) -> None:
    print("\n--- DB row counts ---")
    for table in ["fund_houses", "schemes", "nav_history"]:
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:<20} {n:>10,}")
    print()


def main() -> None:
    csv_file = get_latest_csv(CLEAN_FOLDER)
    print(f"Loading: {csv_file}")

    conn = sqlite3.connect(DB_PATH)
    try:
        setup_db(conn)
        df = load_csv(csv_file)
        print(f"{len(df):,} rows read")
        insert_data(conn, df)
        print_counts(conn)
        print("Done.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
