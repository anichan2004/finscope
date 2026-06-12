"""FinScope dashboard.

Run:  streamlit run app/streamlit_app.py
(Run `python -m scripts.setup_data` first to populate the database.)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# make the src package importable when run via `streamlit run`
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from finscope import (  # noqa: E402
    config,
    data_generator,
    database,
    forecast,
    market_data,
    montecarlo,
    statements,
    variance,
)

st.set_page_config(page_title="FinScope — Personal FP&A", layout="wide")


@st.cache_data(ttl=24 * 3600, show_spinner="Pulling live market data...")
def load_live_assumptions() -> dict:
    """Live S&P 500 return/vol + inflation, cached for a day.

    Falls back to config defaults automatically if the network is
    unavailable (market_data handles the degradation)."""
    import os
    return market_data.derive_assumptions(
        fred_api_key=os.environ.get("FRED_API_KEY")
    )


@st.cache_data
def load_actuals() -> pd.DataFrame:
    conn = database.connect()
    database.init_db(conn)
    actuals = database.monthly_actuals(conn)
    if actuals.empty:
        # First run (e.g. a fresh cloud deploy with no database yet):
        # build the synthetic dataset on the fly so the demo just works.
        df = data_generator.generate_transactions(n_months=24)
        database.load_transactions(conn, df)
        database.load_budgets(conn)
        actuals = database.monthly_actuals(conn)
    conn.close()
    return actuals


actuals = load_actuals()

st.title("FinScope — Personal FP&A Platform")
st.caption("Budget variance · rolling forecast · Monte Carlo planning · financial statements")

tab_var, tab_fc, tab_mc, tab_stmt = st.tabs(
    ["Variance", "Forecast", "Monte Carlo", "Statements & KPIs"]
)

# --- Variance ---------------------------------------------------------------
with tab_var:
    months = sorted(actuals["month"].unique())
    month = st.selectbox("Month", months, index=len(months) - 1)
    report = variance.variance_report(actuals, month=month)
    summary = variance.variance_summary(report)

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Budget", f"${summary['total_budget']:,.0f}")
    c2.metric("Total Actual", f"${summary['total_actual']:,.0f}")
    c3.metric("Variance", f"${summary['total_variance']:,.0f}", summary["status"],
              delta_color="normal" if summary["status"] == "Favorable" else "inverse")

    st.subheader("Variance commentary")
    for line in variance.variance_commentary(actuals, report):
        st.markdown(f"- {line}")

    fig = px.bar(
        report, x="category", y="variance", color="status",
        color_discrete_map={"Favorable": "#2e7d32", "Unfavorable": "#c62828"},
        title="Variance by category (positive = under budget)",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(report, use_container_width=True)

    st.subheader("Spend trend by category")
    trend_cats = st.multiselect(
        "Categories", config.EXPENSE_CATEGORIES,
        default=["Groceries", "Dining", "Travel"],
    )
    if trend_cats:
        trend = actuals[actuals["category"].isin(trend_cats)]
        fig_t = px.line(trend, x="month", y="spend", color="category",
                        markers=True, title="Monthly spend vs. budget (dashed)")
        for cat in trend_cats:
            fig_t.add_hline(y=config.MONTHLY_BUDGET[cat], line_dash="dash",
                            opacity=0.4, annotation_text=f"{cat} budget")
        st.plotly_chart(fig_t, use_container_width=True)

# --- Forecast ---------------------------------------------------------------
with tab_fc:
    horizon = st.slider("Forecast horizon (months)", 3, 18, 12)
    fc = forecast.forecast_cashflow(actuals, horizon=horizon)
    try:
        mape = forecast.backtest_mape(actuals)
        st.metric("Backtest MAPE (production model)", f"{mape:.1%}")
    except ValueError:
        st.info("Not enough history to backtest.")

    fig = go.Figure()
    for kind, color in (("actual", "#1565c0"), ("forecast", "#ef6c00")):
        sub = fc[fc["type"] == kind]
        fig.add_trace(go.Scatter(x=sub["month"], y=sub["actual"],
                                 mode="lines+markers", name=kind, line=dict(color=color)))
    fig.update_layout(title="Monthly net cash flow: actual vs. forecast")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Model selection (6-month holdout backtest)")
    st.caption("The production model must beat the naive baseline to earn its place.")
    try:
        comp = forecast.compare_models(actuals)
        comp["mape"] = comp["mape"].map(lambda m: f"{m:.1%}")
        st.dataframe(comp, use_container_width=True, hide_index=True)
    except ValueError:
        st.info("Not enough history for model comparison.")

# --- Monte Carlo ------------------------------------------------------------
with tab_mc:
    live = load_live_assumptions()
    if live["source"] == "live market data":
        st.caption(f"Defaults estimated from **live {live['ticker']} history** "
                   f"({live['n_months_of_history']} months): "
                   f"return {live['annual_return_mean']:.1%}, "
                   f"vol {live['annual_return_std']:.1%}, "
                   f"inflation {live['annual_inflation']:.1%}.")
    else:
        st.caption("Live market data unavailable — using static defaults.")

    d = config.SIM_DEFAULTS
    col = st.columns(3)
    contrib = col[0].number_input("Monthly contribution ($)", value=float(d["monthly_contribution"]), step=100.0)
    ret = col[1].slider("Expected annual return", 0.0, 0.15,
                        float(min(max(live["annual_return_mean"], 0.0), 0.15)), 0.005)
    goal = col[2].number_input("Goal ($)", value=float(d["goal"]), step=10_000.0)

    res = montecarlo.simulate(
        monthly_contribution=contrib,
        annual_return_mean=ret,
        annual_return_std=live["annual_return_std"],
        annual_inflation=live["annual_inflation"],
        goal=goal,
    )
    st.metric(f"Probability of reaching ${goal:,.0f} in {res.horizon_years} yrs",
              f"{res.prob_goal:.1%}")

    pct = res.percentiles()
    st.write({f"P{k}": f"${v:,.0f}" for k, v in pct.items()})
    fig = px.histogram(x=res.terminal, nbins=60,
                       title="Distribution of terminal net worth (real $)")
    fig.add_vline(x=goal, line_dash="dash", line_color="red")
    st.plotly_chart(fig, use_container_width=True)

# --- Statements -------------------------------------------------------------
with tab_stmt:
    month = actuals["month"].max()
    c1, c2 = st.columns(2)
    c1.subheader("Income Statement")
    c1.dataframe(statements.income_statement(actuals, month), use_container_width=True)
    c2.subheader("Balance Sheet")
    c2.dataframe(statements.balance_sheet(), use_container_width=True)

    st.subheader("Key Metrics")
    k = statements.kpis(actuals, month=month)
    m = st.columns(4)
    m[0].metric("Savings Rate", f"{k['savings_rate']:.1%}")
    m[1].metric("Monthly Burn", f"${k['burn_rate']:,.0f}")
    m[2].metric("Runway", f"{k['runway_months']:.0f} mo")
    m[3].metric("Debt-to-Income", f"{k['debt_to_income']:.2f}")
