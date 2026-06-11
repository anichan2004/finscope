"""Rule-based categorization of transactions from their description text.

A real bank feed gives you a messy description string, not a clean category.
This module maps descriptions to categories with keyword rules, which is the
kind of deterministic, auditable logic finance teams prefer over a black-box
model. The original category is kept so accuracy can be measured.
"""
from __future__ import annotations

import pandas as pd

# Ordered keyword -> category rules. First match wins.
RULES: list[tuple[str, str]] = [
    ("payroll", "Salary"),
    ("interest", "Interest"),
    ("rent", "Housing"),
    ("apartments", "Housing"),
    ("landlord", "Housing"),
    ("energy", "Utilities"),
    ("water", "Utilities"),
    ("xfinity", "Utilities"),
    ("comcast", "Utilities"),
    ("trader joes", "Groceries"),
    ("harris teeter", "Groceries"),
    ("costco", "Groceries"),
    ("whole foods", "Groceries"),
    ("chipotle", "Dining"),
    ("starbucks", "Dining"),
    ("bistro", "Dining"),
    ("doordash", "Dining"),
    ("gas", "Transport"),
    ("uber", "Transport"),
    ("transit", "Transport"),
    ("jiffy", "Transport"),
    ("netflix", "Subscriptions"),
    ("spotify", "Subscriptions"),
    ("icloud", "Subscriptions"),
    ("nytimes", "Subscriptions"),
    ("cvs", "Healthcare"),
    ("family med", "Healthcare"),
    ("dental", "Healthcare"),
    ("amazon", "Shopping"),
    ("target", "Shopping"),
    ("best buy", "Shopping"),
    ("rei", "Shopping"),
    ("air lines", "Travel"),
    ("marriott", "Travel"),
    ("airbnb", "Travel"),
    ("enterprise", "Travel"),
    ("vanguard", "Savings"),
    ("fidelity", "Savings"),
]

UNCATEGORIZED = "Uncategorized"


def categorize_description(description: str) -> str:
    text = description.lower()
    for keyword, category in RULES:
        if keyword in text:
            return category
    return UNCATEGORIZED


def categorize(df: pd.DataFrame, source_col: str = "description") -> pd.DataFrame:
    out = df.copy()
    out["category_predicted"] = out[source_col].map(categorize_description)
    return out


def accuracy(df: pd.DataFrame) -> float:
    """Share of rows where the rule engine matches the true category."""
    if "category" not in df or "category_predicted" not in df:
        raise ValueError("Need both 'category' and 'category_predicted' columns")
    return float((df["category"] == df["category_predicted"]).mean())
