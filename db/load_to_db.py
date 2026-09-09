import sqlite3
import os
import glob
import pandas as pd

DB_PATH = os.path.join("data", "nav.db")
SCHEMA_PATH = os.path.join("db", "schema.sql")
CLEAN_FOLDER = os.path.join("data", "clean")
def get_latest_csv(folder):
    files = glob.glob(os.path.join(folder, "*.csv"))
    if not files:
        raise FileNotFoundError(f"no csv files in {folder}")
    return max(files, key=os.path.getmtime)

def setup_db(conn):
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        sql = f.read()
    conn.executescript(sql)
    conn.commit()


def load_csv(path):
    df = pd.read_csv(path, dtype={"scheme_code": str})
    df["nav_date"] = pd.to_datetime(df["nav_date"]).dt.strftime("%Y-%m-%d")
    return df


def insert_data(conn, df):
    cur = conn.cursor()
    seen_houses = {}
    for _, row in df.iterrows():
        house = row["fund_house"]
        code = row["scheme_code"]
        nav = float(row["nav"])
        nav_date = row["nav_date"]
        isin_g = row["isin_growth"]
        isin_r = row["isin_reinvest"]
        name = row["scheme_name"]

        if house not in seen_houses:
            cur.execute("INSERT OR IGNORE INTO fund_houses (fund_house_name) VALUES (?)", (house,))
            cur.execute("SELECT fund_house_id FROM fund_houses WHERE fund_house_name = ?", (house,))
            result = cur.fetchone()
            seen_houses[house] = result[0]
        house_id = seen_houses[house]
        cur.execute("INSERT OR IGNORE INTO schemes (scheme_code, fund_house_id, isin_growth, isin_reinvest, scheme_name) VALUES (?, ?, ?, ?, ?)",
                    (code, house_id, isin_g, isin_r, name))
        cur.execute("INSERT OR IGNORE INTO nav_history (scheme_code, nav, nav_date) VALUES (?, ?, ?)",
                    (code, nav, nav_date))
    conn.commit()


def print_counts(conn):
    print("\n--- DB Summary ---")
    for table in ["fund_houses", "schemes", "nav_history"]:
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table}: {n:,} rows")
    print("------------------\n")


def main():
    csv_file = get_latest_csv(CLEAN_FOLDER)
    print(f"using file: {csv_file}")

    conn = sqlite3.connect(DB_PATH)

    try:
        setup_db(conn)
        df = load_csv(csv_file)
        print(f"total rows: {len(df):,}")
        insert_data(conn, df)
        print_counts(conn)
        print("done loading data")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
