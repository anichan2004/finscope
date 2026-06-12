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
    edgar,
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


@st.cache_data(ttl=24 * 3600, show_spinner="Fetching SEC filings...")
def load_company(ticker: str):
    return edgar.get_company_financials(ticker)


actuals = load_actuals()

st.title("FinScope — Personal FP&A Platform")
st.caption("Budget variance · rolling forecast · Monte Carlo planning · financial statements · real company analysis")

tab_var, tab_fc, tab_mc, tab_stmt, tab_co = st.tabs(
    ["Variance", "Forecast", "Monte Carlo", "Statements & KPIs", "Company Analysis"]
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
    st.caption("Champion/challenger: production auto-ships whichever model wins "
               "the backtest. A seasonal challenger was tested and **lost** — "
               "with limited history, estimating 12 monthly indices overfits "
               "noise in 10 months to capture signal in 2. The simpler model "
               "keeps its job until the evidence says otherwise.")
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

# --- Company Analysis (real SEC EDGAR data) ---------------------------------
with tab_co:
    st.markdown(
        "Analyze any US public company using its **actual SEC filings** "
        "(10-Q / 10-K via the free EDGAR API). Same FP&A toolkit, real data."
    )
    ticker = st.text_input("Ticker", value="AAPL", max_chars=6).strip().upper()

    if ticker:
        try:
            name, fin = load_company(ticker)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not load {ticker}: {exc}")
            fin = pd.DataFrame()
            name = ticker

        if fin.empty or "revenue" not in fin or fin["revenue"].dropna().empty:
            if not fin.empty:
                st.warning("Filings found, but revenue could not be mapped "
                           "for this company's tagging.")
        else:
            rev = fin["revenue"].dropna()
            latest_q = rev.index[-1].date()
            g = edgar.qoq_yoy(fin, "revenue")
            yoy = g["yoy_growth"].iloc[-1] if not g.empty else float("nan")

            st.subheader(f"{name} — quarterly fundamentals "
                         f"(latest: {latest_q})")
            c1, c2, c3 = st.columns(3)
            c1.metric("Revenue (latest Q)", f"${rev.iloc[-1]/1e9:,.1f}B")
            if pd.notna(yoy):
                c2.metric("Revenue YoY", f"{yoy:+.1%}",
                          delta_color="normal" if yoy >= 0 else "inverse")
            if "net_margin" in fin and fin["net_margin"].notna().any():
                c3.metric("Net Margin (latest Q)",
                          f"{fin['net_margin'].dropna().iloc[-1]:.1%}")

            # Revenue & net income trend
            plot_df = fin.reset_index()
            fig = go.Figure()
            fig.add_trace(go.Bar(x=plot_df["quarter_end"], y=plot_df["revenue"],
                                 name="Revenue", marker_color="#1565c0"))
            if "net_income" in fin:
                fig.add_trace(go.Scatter(x=plot_df["quarter_end"],
                                         y=plot_df["net_income"],
                                         name="Net income", mode="lines+markers",
                                         line=dict(color="#ef6c00")))
            fig.update_layout(title="Revenue and net income by quarter (USD)")
            st.plotly_chart(fig, use_container_width=True)

            # Margins
            margin_cols = [c for c in ("gross_margin", "operating_margin",
                                       "net_margin") if c in fin]
            if margin_cols:
                mfig = px.line(plot_df, x="quarter_end", y=margin_cols,
                               markers=True, title="Margin trend")
                mfig.update_layout(yaxis_tickformat=".0%")
                st.plotly_chart(mfig, use_container_width=True)

            # Growth variance table -- the earnings-cycle view
            st.subheader("Growth analysis (QoQ / YoY)")
            gt = g.copy()
            gt.index = gt.index.date
            gt["revenue"] = gt["revenue"].map(lambda v: f"${v/1e9:,.2f}B")
            for col in ("qoq_growth", "yoy_growth"):
                gt[col] = gt[col].map(
                    lambda v: f"{v:+.1%}" if pd.notna(v) else "—")
            st.dataframe(gt.tail(8), use_container_width=True)

            # Revenue forecast with the model bake-off, on REAL data
            st.subheader("Revenue forecast (next 4 quarters)")
            if len(rev) >= 10:
                rev_q = rev.copy()
                rev_q.index = pd.PeriodIndex(rev_q.index, freq="Q")
                fc_q = forecast.exp_smoothing_forecast(rev_q, horizon=4, freq="Q")

                hold = 4
                train, test = rev_q.iloc[:-hold], rev_q.iloc[-hold:]
                pred = forecast.exp_smoothing_forecast(train, horizon=hold, freq="Q")
                mape_q = forecast._mape(test.to_numpy(dtype=float),
                                        pred.to_numpy(dtype=float))
                st.metric("Backtest MAPE (last 4 quarters held out)",
                          f"{mape_q:.1%}")

                ffig = go.Figure()
                ffig.add_trace(go.Scatter(x=rev_q.index.astype(str), y=rev_q.values,
                                          name="actual", mode="lines+markers",
                                          line=dict(color="#1565c0")))
                ffig.add_trace(go.Scatter(x=fc_q.index.astype(str), y=fc_q.values,
                                          name="forecast", mode="lines+markers",
                                          line=dict(color="#ef6c00", dash="dot")))
                ffig.update_layout(title="Quarterly revenue: actual vs. forecast")
                st.plotly_chart(ffig, use_container_width=True)
            else:
                st.info("Not enough quarterly history to forecast.")

            st.caption("Source: SEC EDGAR company facts (10-Q/10-K filings). "
                       "Q4 figures derived as FY minus reported quarters where "
                       "not filed directly.")
