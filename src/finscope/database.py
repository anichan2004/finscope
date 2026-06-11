"""SQLite persistence layer.

The schema is written so it would port to Postgres with minimal change
(standard types, no SQLite-only tricks). Analysts get screened on SQL, so the
monthly aggregation that feeds the rest of the app is done in SQL on purpose.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    txn_date    TEXT    NOT NULL,
    description TEXT    NOT NULL,
    category    TEXT    NOT NULL,
    amount      REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS budgets (
    category       TEXT PRIMARY KEY,
    monthly_budget REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_txn_date ON transactions(txn_date);
CREATE INDEX IF NOT EXISTS idx_txn_cat  ON transactions(category);
"""

MONTHLY_ACTUALS_SQL = """
SELECT
    strftime('%Y-%m', txn_date) AS month,
    category,
    ROUND(SUM(amount), 2)       AS net_amount,
    ROUND(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 2) AS spend
FROM transactions
GROUP BY month, category
ORDER BY month, category;
"""


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(path)


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def load_transactions(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    rows = df.copy()
    rows["txn_date"] = pd.to_datetime(rows["date"]).dt.strftime("%Y-%m-%d")
    rows = rows[["txn_date", "description", "category", "amount"]]
    conn.execute("DELETE FROM transactions")
    rows.to_sql("transactions", conn, if_exists="append", index=False)
    conn.commit()
    return len(rows)


def load_budgets(conn: sqlite3.Connection, budget: dict[str, float] | None = None) -> None:
    budget = budget or config.MONTHLY_BUDGET
    conn.execute("DELETE FROM budgets")
    conn.executemany(
        "INSERT INTO budgets (category, monthly_budget) VALUES (?, ?)",
        list(budget.items()),
    )
    conn.commit()


def monthly_actuals(conn: sqlite3.Connection) -> pd.DataFrame:
    """Aggregate spend by month and category (the SQL-side rollup)."""
    return pd.read_sql_query(MONTHLY_ACTUALS_SQL, conn)


def get_budgets(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query("SELECT * FROM budgets", conn)
