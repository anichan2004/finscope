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


def variance_commentary(
    actuals: pd.DataFrame,
    report: pd.DataFrame,
    threshold: float = 0.10,
    trailing_months: int = 3,
) -> list[str]:
    """Auto-generate analyst-style commentary for material variances.

    A variance is "material" when |variance %| >= threshold. Each line
    states the driver by comparing the month's actual to the trailing
    n-month average -- the same structure a human analyst uses:
    what happened, how big, and versus what norm.
    """
    if report.empty:
        return []

    month = report["month"].iloc[0]
    exp = actuals[actuals["category"].isin(config.EXPENSE_CATEGORIES)]
    months_sorted = sorted(exp["month"].unique())
    if month not in months_sorted:
        return []
    idx = months_sorted.index(month)
    trail = months_sorted[max(0, idx - trailing_months):idx]

    lines: list[str] = []
    material = report[report["variance_pct"].abs() >= threshold]
    # biggest dollar impact first
    material = material.reindex(material["variance"].abs().sort_values(ascending=False).index)

    for _, r in material.iterrows():
        cat, var, pct = r["category"], r["variance"], r["variance_pct"]
        direction = "under" if var >= 0 else "over"
        line = (f"{cat}: {'favorable' if var >= 0 else 'unfavorable'} by "
                f"${abs(var):,.0f} ({abs(pct):.0%} {direction} budget)")

        if trail:
            avg = exp[(exp["category"] == cat) & (exp["month"].isin(trail))]["spend"].mean()
            if avg and avg > 0:
                delta = (r["actual"] - avg) / avg
                if abs(delta) >= 0.05:
                    line += (f"; spend ran {abs(delta):.0%} "
                             f"{'above' if delta > 0 else 'below'} the trailing "
                             f"{len(trail)}-month average")
                else:
                    line += "; in line with the recent run-rate, variance is vs. plan"
        lines.append(line + ".")

    if not lines:
        lines.append(f"No material variances (threshold ±{threshold:.0%}) in {month}; "
                     "spending tracked close to plan across all categories.")
    return lines
