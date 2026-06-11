"""End-to-end setup: generate synthetic data, categorize, load to SQLite,
and emit a sample Excel variance report. Run this once before launching the
dashboard.

    python -m scripts.setup_data
"""
from __future__ import annotations

import os

from finscope import (
    categorize,
    config,
    data_generator,
    database,
    excel_report,
    forecast,
    market_data,
    montecarlo,
    variance,
)


def main() -> None:
    print("1. Generating synthetic transactions...")
    df = data_generator.generate_transactions(n_months=24)
    print(f"   {len(df)} transactions generated.")

    print("2. Categorizing from descriptions...")
    cat = categorize.categorize(df)
    print(f"   rule-based categorization accuracy: {categorize.accuracy(cat):.1%}")

    print("3. Loading into SQLite...")
    conn = database.connect()
    database.init_db(conn)
    n = database.load_transactions(conn, df)
    database.load_budgets(conn)
    print(f"   {n} rows persisted to {config.DB_PATH}")

    print("4. Building variance report + forecast...")
    actuals = database.monthly_actuals(conn)
    report = variance.variance_report(actuals)
    summary = variance.variance_summary(report)
    mape = forecast.backtest_mape(actuals)
    print(f"   latest-month total variance: ${summary['total_variance']:,.0f} "
          f"({summary['status']})")
    print(f"   forecast backtest MAPE: {mape:.1%}")

    print("5. Pulling LIVE market + macro data for the planning model...")
    assumptions = market_data.derive_assumptions(
        fred_api_key=os.environ.get("FRED_API_KEY")
    )
    print(f"   source: {assumptions['source']} "
          f"({assumptions['n_months_of_history']} months of history)")
    print(f"   expected return: {assumptions['annual_return_mean']:.1%} | "
          f"vol: {assumptions['annual_return_std']:.1%} | "
          f"inflation: {assumptions['annual_inflation']:.1%}")
    res = montecarlo.simulate(
        annual_return_mean=assumptions["annual_return_mean"],
        annual_return_std=assumptions["annual_return_std"],
        annual_inflation=assumptions["annual_inflation"],
    )
    print(f"   probability of reaching ${res.goal:,.0f} in "
          f"{res.horizon_years} yrs: {res.prob_goal:.1%}")

    out = config.DATA_DIR / "variance_report.xlsx"
    excel_report.export_variance_report(report, out)
    print(f"6. Excel report written to {out}")

    conn.close()
    print("\nDone. Launch the dashboard with:  streamlit run app/streamlit_app.py")


if __name__ == "__main__":
    main()
