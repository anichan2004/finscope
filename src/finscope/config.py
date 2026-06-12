"""Central configuration: categories, default budgets, paths, and assumptions.

Keeping these in one place makes the project easy to audit and lets the
dashboard, the variance engine, and the tests all agree on the same numbers.
"""
from __future__ import annotations

from pathlib import Path

# --- Paths -----------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "finscope.db"

# --- Spending categories ---------------------------------------------------
# These mirror how an FP&A team would build a chart of accounts: fixed vs.
# variable cost behavior matters for forecasting and variance explanations.
INCOME_CATEGORIES = ["Salary", "Interest", "Other Income"]

EXPENSE_CATEGORIES = [
    "Housing",        # fixed
    "Utilities",      # semi-fixed
    "Groceries",      # variable
    "Dining",         # variable / discretionary
    "Transport",      # variable
    "Subscriptions",  # fixed / discretionary
    "Healthcare",     # variable
    "Shopping",       # discretionary
    "Travel",         # seasonal / discretionary
    "Savings",        # transfer to investments
]

# Cost behavior tags drive how each category is forecast.
FIXED_CATEGORIES = {"Housing", "Subscriptions"}
SEASONAL_CATEGORIES = {"Travel", "Shopping"}  # spike in Nov/Dec

# --- Monthly budget plan (USD) --------------------------------------------
MONTHLY_BUDGET = {
    "Housing": 1800,
    "Utilities": 220,
    "Groceries": 600,
    "Dining": 350,
    "Transport": 250,
    "Subscriptions": 75,
    "Healthcare": 180,
    "Shopping": 300,
    "Travel": 250,
    "Savings": 1200,
}

# --- Monte Carlo defaults --------------------------------------------------
SIM_DEFAULTS = {
    "starting_net_worth": 25_000.0,
    "monthly_contribution": 1_200.0,
    "annual_return_mean": 0.07,   # nominal expected return
    "annual_return_std": 0.15,    # volatility
    "annual_inflation": 0.03,
    "horizon_years": 20,
    "goal": 750_000.0,
    "n_simulations": 10_000,
}

# --- Investment watchlist ----------------------------------------------------
# The personal balance sheet carries an investments line; this watchlist is
# the research universe for those holdings -- the companies behind the money.
# Used by the Portfolio Research page (SEC EDGAR analysis).
WATCHLIST = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "GOOGL": "Alphabet",
    "AMZN": "Amazon",
    "NVDA": "NVIDIA",
    "JPM": "JPMorgan Chase",
    "JNJ": "Johnson & Johnson",
    "WMT": "Walmart",
    "KO": "Coca-Cola",
    "XOM": "ExxonMobil",
}
