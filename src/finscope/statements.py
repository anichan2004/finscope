"""Recast personal finances into the three core financial statements + KPIs.

This is the most "analyst" piece of the project: it treats a household like a
small business with an income statement, a balance sheet, and a cash-flow
summary, then derives the KPIs a lender or planner would actually look at.
Asset/liability balances are supplied as inputs since they don't live in the
transaction feed.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from . import config


@dataclass
class BalanceSheetInputs:
    cash: float = 18_000.0
    investments: float = 25_000.0
    other_assets: float = 5_000.0
    credit_card_debt: float = 3_500.0
    student_loans: float = 14_000.0
    other_liabilities: float = 0.0


def income_statement(actuals: pd.DataFrame, month: str | None = None) -> pd.DataFrame:
    """Income vs. expenses for a month; net = personal 'profit'."""
    month = month or actuals["month"].max()
    snap = actuals[actuals["month"] == month]

    income = snap[snap["category"].isin(config.INCOME_CATEGORIES)]["net_amount"].sum()
    expense = -snap[snap["category"].isin(config.EXPENSE_CATEGORIES)]["net_amount"].sum()
    net = income - expense

    return pd.DataFrame(
        {
            "line_item": ["Total Income", "Total Expenses", "Net Income"],
            "amount": [round(income, 2), round(expense, 2), round(net, 2)],
        }
    )


def balance_sheet(inputs: BalanceSheetInputs | None = None) -> pd.DataFrame:
    b = inputs or BalanceSheetInputs()
    assets = b.cash + b.investments + b.other_assets
    liabilities = b.credit_card_debt + b.student_loans + b.other_liabilities
    net_worth = assets - liabilities
    return pd.DataFrame(
        {
            "line_item": [
                "Cash", "Investments", "Other Assets", "Total Assets",
                "Credit Card Debt", "Student Loans", "Other Liabilities",
                "Total Liabilities", "Net Worth",
            ],
            "amount": [
                b.cash, b.investments, b.other_assets, assets,
                b.credit_card_debt, b.student_loans, b.other_liabilities,
                liabilities, net_worth,
            ],
        }
    )


def kpis(
    actuals: pd.DataFrame,
    bs_inputs: BalanceSheetInputs | None = None,
    month: str | None = None,
) -> dict[str, float]:
    bs = bs_inputs or BalanceSheetInputs()
    inc = income_statement(actuals, month)
    income = float(inc.loc[inc["line_item"] == "Total Income", "amount"].iloc[0])
    expense = float(inc.loc[inc["line_item"] == "Total Expenses", "amount"].iloc[0])
    net = income - expense

    liquid = bs.cash + bs.investments
    liabilities = bs.credit_card_debt + bs.student_loans + bs.other_liabilities

    return {
        "savings_rate": round(net / income, 4) if income else 0.0,
        "burn_rate": round(expense, 2),
        "runway_months": round(liquid / expense, 1) if expense else float("inf"),
        "debt_to_income": round(liabilities / (income * 12), 4) if income else 0.0,
        "net_income": round(net, 2),
    }
