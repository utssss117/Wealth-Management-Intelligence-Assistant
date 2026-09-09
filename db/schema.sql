CREATE TABLE IF NOT EXISTS fund_houses (
    fund_house_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_house_name TEXT    NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS schemes (
    scheme_code   TEXT    PRIMARY KEY,          
    fund_house_id INTEGER NOT NULL,
    isin_growth   TEXT,
    isin_reinvest TEXT,
    scheme_name   TEXT    NOT NULL,
    FOREIGN KEY (fund_house_id) REFERENCES fund_houses (fund_house_id)
);

CREATE TABLE IF NOT EXISTS nav_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_code TEXT    NOT NULL,
    nav         REAL    NOT NULL,
    nav_date    TEXT    NOT NULL,              
    FOREIGN KEY (scheme_code) REFERENCES schemes (scheme_code),
    UNIQUE (scheme_code, nav_date)
);
