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
    database,
    forecast,
    montecarlo,
    statements,
    variance,
)

st.set_page_config(page_title="FinScope — Personal FP&A", layout="wide")


@st.cache_data
def load_actuals() -> pd.DataFrame:
    conn = database.connect()
    database.init_db(conn)
    actuals = database.monthly_actuals(conn)
    conn.close()
    return actuals


actuals = load_actuals()
if actuals.empty:
    st.error("No data found. Run `python -m scripts.setup_data` first.")
    st.stop()

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
    c3.metric("Variance", f"${summary['total_variance']:,.0f}", summary["status"])

    fig = px.bar(
        report, x="category", y="variance", color="status",
        color_discrete_map={"Favorable": "#2e7d32", "Unfavorable": "#c62828"},
        title="Variance by category (positive = under budget)",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(report, use_container_width=True)

# --- Forecast ---------------------------------------------------------------
with tab_fc:
    horizon = st.slider("Forecast horizon (months)", 3, 18, 12)
    fc = forecast.forecast_cashflow(actuals, horizon=horizon)
    try:
        mape = forecast.backtest_mape(actuals)
        st.metric("Backtest MAPE", f"{mape:.1%}")
    except ValueError:
        st.info("Not enough history to backtest.")

    fig = go.Figure()
    for kind, color in (("actual", "#1565c0"), ("forecast", "#ef6c00")):
        sub = fc[fc["type"] == kind]
        fig.add_trace(go.Scatter(x=sub["month"], y=sub["actual"],
                                 mode="lines+markers", name=kind, line=dict(color=color)))
    fig.update_layout(title="Monthly net cash flow: actual vs. forecast")
    st.plotly_chart(fig, use_container_width=True)

# --- Monte Carlo ------------------------------------------------------------
with tab_mc:
    d = config.SIM_DEFAULTS
    col = st.columns(3)
    contrib = col[0].number_input("Monthly contribution ($)", value=float(d["monthly_contribution"]), step=100.0)
    ret = col[1].slider("Expected annual return", 0.0, 0.15, d["annual_return_mean"], 0.005)
    goal = col[2].number_input("Goal ($)", value=float(d["goal"]), step=10_000.0)

    res = montecarlo.simulate(monthly_contribution=contrib, annual_return_mean=ret, goal=goal)
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
