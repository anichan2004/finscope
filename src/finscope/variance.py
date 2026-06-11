"""Budget vs. Actual variance analysis -- the core FP&A deliverable.

Convention: for expense categories, "favorable" means spending LESS than
budget. Variance = budget - actual_spend, so a positive variance is favorable.
This matches how a real variance report reads.
"""
from __future__ import annotations

import pandas as pd

from . import config


def variance_report(
    actuals: pd.DataFrame,
    budget: dict[str, float] | None = None,
    month: str | None = None,
) -> pd.DataFrame:
    """Build a per-category variance table for a given month.

    `actuals` is the output of database.monthly_actuals (columns: month,
    category, net_amount, spend). If `month` is None the latest month is used.
    """
    budget = budget or config.MONTHLY_BUDGET
    exp = actuals[actuals["category"].isin(config.EXPENSE_CATEGORIES)].copy()
    if exp.empty:
        return pd.DataFrame()

    month = month or exp["month"].max()
    snapshot = exp[exp["month"] == month][["category", "spend"]]

    report = (
        pd.DataFrame({"category": list(budget.keys())})
        .merge(snapshot, on="category", how="left")
        .fillna({"spend": 0.0})
    )
    report["budget"] = report["category"].map(budget)
    report["actual"] = report["spend"]
    report["variance"] = report["budget"] - report["actual"]
    report["variance_pct"] = report["variance"] / report["budget"].replace(0, pd.NA)
    report["status"] = report["variance"].apply(
        lambda v: "Favorable" if v >= 0 else "Unfavorable"
    )
    report["month"] = month

    cols = ["month", "category", "budget", "actual", "variance",
            "variance_pct", "status"]
    return report[cols].sort_values("variance").reset_index(drop=True)


def variance_summary(report: pd.DataFrame) -> dict[str, float]:
    """Totals row an analyst would put at the bottom of the report."""
    if report.empty:
        return {}
    total_budget = float(report["budget"].sum())
    total_actual = float(report["actual"].sum())
    total_var = total_budget - total_actual
    return {
        "total_budget": round(total_budget, 2),
        "total_actual": round(total_actual, 2),
        "total_variance": round(total_var, 2),
        "total_variance_pct": round(total_var / total_budget, 4) if total_budget else 0.0,
        "status": "Favorable" if total_var >= 0 else "Unfavorable",
    }
