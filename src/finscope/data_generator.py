"""Generate realistic synthetic transaction data.

Using synthetic data keeps real bank statements out of the repo while still
exercising every part of the pipeline. Patterns are intentionally varied:
recurring fixed bills, variable spend with noise, seasonal spikes, and a
monthly salary, so the forecasting and variance modules have something
meaningful to chew on.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

# Merchant pools per category -> let the rule-based categorizer infer the
# category from a free-text description, mimicking a real bank feed.
MERCHANTS = {
    "Housing": ["Maple Grove Apartments", "Greystar Rent", "Landlord ACH"],
    "Utilities": ["Duke Energy", "City Water Dept", "Comcast Xfinity"],
    "Groceries": ["Trader Joes", "Harris Teeter", "Costco", "Whole Foods"],
    "Dining": ["Chipotle", "Starbucks", "The Local Bistro", "DoorDash"],
    "Transport": ["Shell Gas", "Uber Trip", "City Transit", "Jiffy Lube"],
    "Subscriptions": ["Netflix", "Spotify", "iCloud", "NYTimes"],
    "Healthcare": ["CVS Pharmacy", "Apex Family Med", "Delta Dental"],
    "Shopping": ["Amazon", "Target", "Best Buy", "REI"],
    "Travel": ["Delta Air Lines", "Marriott", "Airbnb", "Enterprise Rent"],
    "Savings": ["Vanguard Transfer", "Fidelity ACH"],
    "Salary": ["ACME Corp Payroll"],
    "Interest": ["Ally Bank Interest"],
}


def _month_starts(n_months: int, end: pd.Timestamp) -> list[pd.Timestamp]:
    start = (end - pd.DateOffset(months=n_months - 1)).replace(day=1)
    return list(pd.date_range(start=start, periods=n_months, freq="MS"))


def generate_transactions(
    n_months: int = 24,
    end: str | pd.Timestamp | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    """Return a tidy transaction DataFrame.

    Columns: date, description, category, amount (income positive,
    expenses negative).
    """
    rng = np.random.default_rng(seed)
    end_ts = pd.Timestamp(end) if end is not None else pd.Timestamp.today().normalize()
    rows: list[dict] = []

    for month_start in _month_starts(n_months, end_ts):
        month_idx = month_start.month
        seasonal = 1.0 + (0.6 if month_idx in (11, 12) else 0.0)

        # --- Income: salary on the 1st, occasional interest --------------
        rows.append(
            dict(
                date=month_start,
                description=rng.choice(MERCHANTS["Salary"]),
                category="Salary",
                amount=round(float(rng.normal(6200, 120)), 2),
            )
        )
        if rng.random() < 0.8:
            rows.append(
                dict(
                    date=month_start + pd.Timedelta(days=2),
                    description=MERCHANTS["Interest"][0],
                    category="Interest",
                    amount=round(float(rng.uniform(5, 35)), 2),
                )
            )

        # --- Expenses by category ---------------------------------------
        for cat in config.EXPENSE_CATEGORIES:
            budget = config.MONTHLY_BUDGET[cat]

            if cat in config.FIXED_CATEGORIES:
                # one predictable charge near the start of the month
                amt = budget * float(rng.normal(1.0, 0.01))
                rows.append(
                    dict(
                        date=month_start + pd.Timedelta(days=int(rng.integers(1, 4))),
                        description=rng.choice(MERCHANTS[cat]),
                        category=cat,
                        amount=-round(amt, 2),
                    )
                )
                continue

            mult = seasonal if cat in config.SEASONAL_CATEGORIES else 1.0
            # spread variable spend across several charges in the month
            n_txn = int(rng.integers(3, 9))
            target = budget * mult * float(rng.normal(1.0, 0.12))
            weights = rng.dirichlet(np.ones(n_txn))
            for w in weights:
                day = int(rng.integers(1, 28))
                rows.append(
                    dict(
                        date=month_start + pd.Timedelta(days=day),
                        description=rng.choice(MERCHANTS[cat]),
                        category=cat,
                        amount=-round(target * w, 2),
                    )
                )

    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])
    return df


if __name__ == "__main__":
    sample = generate_transactions()
    print(sample.head())
    print(f"\n{len(sample)} transactions across "
          f"{sample['date'].dt.to_period('M').nunique()} months")
