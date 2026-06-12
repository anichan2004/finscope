"""FinScope — professional multipage dashboard.

Run:  streamlit run app/streamlit_app.py

Information architecture:
    Overview          executive summary landing page
    Personal FP&A     Variance / Forecast / Planning / Statements
    Markets           Company Analysis (SEC EDGAR)

Design system: Inter typography, one Plotly template (style_fig) applied to
every chart, consistent $/% formatting, KPI cards.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from finscope import (  # noqa: E402
    config,
    data_generator,
    database,
    edgar,
    excel_report,
    forecast,
    market_data,
    montecarlo,
    statements,
    variance,
)

# ===========================================================================
# Design system
# ===========================================================================

ACCENT = "#10b981"
BLUE = "#3b82f6"
AMBER = "#f59e0b"
RED = "#ef4444"
GREEN_FAV = "#2e7d32"
RED_UNFAV = "#c62828"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* KPI cards */
[data-testid="stMetric"] {
    background: #1a1f2b;
    border: 1px solid #2a3142;
    border-radius: 10px;
    padding: 14px 18px;
}
[data-testid="stMetricLabel"] { font-size: 0.82rem; opacity: 0.85; }

/* Tighter page top */
.block-container { padding-top: 2.2rem; }

h1 { font-weight: 700; letter-spacing: -0.02em; }
h2, h3 { font-weight: 600; letter-spacing: -0.01em; }

/* Subtle horizontal rules */
hr { border-color: #2a3142; }
</style>
"""


def style_fig(fig: go.Figure, height: int = 380) -> go.Figure:
    """One chart language for the whole app."""
    fig.update_layout(
        template="plotly_dark",
        colorway=[ACCENT, BLUE, AMBER, RED],
        font=dict(family="Inter, sans-serif", size=13),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=height,
        margin=dict(t=48, r=16, b=8, l=8),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    fig.update_xaxes(gridcolor="#222838", zeroline=False)
    fig.update_yaxes(gridcolor="#222838", zeroline=False)
    return fig


def money(x: float) -> str:
    return f"${x:,.0f}"


# ===========================================================================
# Data loaders
# ===========================================================================

@st.cache_data
def load_actuals() -> pd.DataFrame:
    conn = database.connect()
    database.init_db(conn)
    actuals = database.monthly_actuals(conn)
    if actuals.empty:
        df = data_generator.generate_transactions(n_months=24)
        database.load_transactions(conn, df)
        database.load_budgets(conn)
        actuals = database.monthly_actuals(conn)
    conn.close()
    return actuals


@st.cache_data(ttl=24 * 3600, show_spinner="Pulling live market data...")
def load_live_assumptions() -> dict:
    data = market_data.derive_assumptions(
        fred_api_key=os.environ.get("FRED_API_KEY")
    )
    if data["source"] != "live market data":
        load_live_assumptions.clear()  # never cache a failure
    return data


@st.cache_data(ttl=24 * 3600, show_spinner="Fetching SEC filings...")
def load_company(ticker: str):
    return edgar.get_company_financials(ticker)


# ===========================================================================
# Pages
# ===========================================================================

def page_overview() -> None:
    st.title("FinScope")
    st.caption("Personal FP&A platform — corporate finance methods applied to "
               "personal finances, plus real-market company analysis.")

    actuals = load_actuals()
    month = actuals["month"].max()
    report = variance.variance_report(actuals, month=month)
    summary = variance.variance_summary(report)
    k = statements.kpis(actuals, month=month)

    st.subheader(f"This month at a glance — {month}")
    c = st.columns(4)
    c[0].metric("Net Income", money(k["net_income"]),
                help="Income minus expenses for the month.")
    c[1].metric("Savings Rate", f"{k['savings_rate']:.1%}",
                help="Net income ÷ income. Advisors commonly target 20%+.")
    c[2].metric("Budget Variance", money(summary["total_variance"]),
                summary["status"],
                delta_color="normal" if summary["status"] == "Favorable" else "inverse",
                help="Budget − actual across all categories.")
    c[3].metric("Runway", f"{k['runway_months']:.0f} mo",
                help="Months liquid assets last at current burn if income stops.")

    left, right = st.columns(2)

    with left:
        fc = forecast.forecast_cashflow(actuals, horizon=6)
        fig = go.Figure()
        for kind, color in (("actual", BLUE), ("forecast", AMBER)):
            sub = fc[fc["type"] == kind]
            fig.add_trace(go.Scatter(x=sub["month"], y=sub["actual"],
                                     mode="lines+markers", name=kind,
                                     line=dict(color=color)))
        fig.update_layout(title="Net cash flow — trailing 24 months + forecast")
        st.plotly_chart(style_fig(fig, 330), use_container_width=True)

    with right:
        movers = report.reindex(
            report["variance"].abs().sort_values(ascending=False).index
        ).head(5)
        fig = px.bar(movers, x="variance", y="category", orientation="h",
                     color="status",
                     color_discrete_map={"Favorable": GREEN_FAV,
                                         "Unfavorable": RED_UNFAV},
                     title="Top variance movers this month")
        st.plotly_chart(style_fig(fig, 330), use_container_width=True)

    st.markdown("---")
    st.markdown("**Data sources** &nbsp;·&nbsp; Transactions: synthetic "
                "*(by design — bank data is private; Plaid is the production "
                "path)* &nbsp;·&nbsp; S&P 500: 🟢 live &nbsp;·&nbsp; "
                "Inflation: 🟢 live (FRED) &nbsp;·&nbsp; Filings: 🟢 live "
                "(SEC EDGAR)")
    st.caption("Built with Python · pandas · SQL · Streamlit · pytest · "
               "GitHub Actions CI — "
               "[source on GitHub](https://github.com/anichan2004/finscope)")


def page_variance() -> None:
    st.title("Budget vs. Actual")
    actuals = load_actuals()

    months = sorted(actuals["month"].unique())
    month = st.selectbox("Month", months, index=len(months) - 1)
    report = variance.variance_report(actuals, month=month)
    summary = variance.variance_summary(report)

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Budget", money(summary["total_budget"]),
              help="Sum of the monthly plan across all expense categories.")
    c2.metric("Total Actual", money(summary["total_actual"]),
              help="What was actually spent this month.")
    c3.metric("Variance", money(summary["total_variance"]), summary["status"],
              delta_color="normal" if summary["status"] == "Favorable" else "inverse",
              help="Budget − Actual. Positive = favorable (under budget).")

    with st.expander("How is this calculated?"):
        st.markdown(
            "Variance = **budget − actual** per category, so positive is "
            "favorable. Commentary flags variances beyond ±10% and compares "
            "the month to the trailing 3-month average to separate one-off "
            "blips from developing trends."
        )

    st.subheader("Commentary")
    for line in variance.variance_commentary(actuals, report):
        st.markdown(f"- {line}")

    fig = px.bar(report, x="category", y="variance", color="status",
                 color_discrete_map={"Favorable": GREEN_FAV,
                                     "Unfavorable": RED_UNFAV},
                 title="Variance by category (positive = under budget)")
    st.plotly_chart(style_fig(fig), use_container_width=True)

    disp = report.drop(columns=["month"]).copy()
    disp["variance_pct"] = disp["variance_pct"] * 100
    st.dataframe(
        disp, use_container_width=True, hide_index=True,
        column_config={
            "category": st.column_config.TextColumn("Category"),
            "budget": st.column_config.NumberColumn("Budget", format="$%.0f"),
            "actual": st.column_config.NumberColumn("Actual", format="$%.0f"),
            "variance": st.column_config.NumberColumn("Variance", format="$%.0f"),
            "variance_pct": st.column_config.NumberColumn("Variance %",
                                                          format="%.1f%%"),
            "status": st.column_config.TextColumn("Status"),
        },
    )

    xlsx_path = Path(tempfile.gettempdir()) / f"variance_{month}.xlsx"
    excel_report.export_variance_report(report, xlsx_path)
    st.download_button(
        "⬇️ Download formatted Excel variance report",
        data=xlsx_path.read_bytes(),
        file_name=f"FinScope_variance_{month}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        help="Color-coded workbook generated with openpyxl.",
    )

    st.subheader("Spend trend by category")
    trend_cats = st.multiselect("Categories", config.EXPENSE_CATEGORIES,
                                default=["Groceries", "Dining", "Travel"])
    if trend_cats:
        trend = actuals[actuals["category"].isin(trend_cats)]
        fig_t = px.line(trend, x="month", y="spend", color="category",
                        markers=True, title="Monthly spend vs. budget (dashed)")
        for cat in trend_cats:
            fig_t.add_hline(y=config.MONTHLY_BUDGET[cat], line_dash="dash",
                            opacity=0.4, annotation_text=f"{cat} budget")
        st.plotly_chart(style_fig(fig_t), use_container_width=True)


def page_forecast() -> None:
    st.title("Rolling Forecast")
    actuals = load_actuals()

    horizon = st.slider("Forecast horizon (months)", 3, 18, 12)
    fc = forecast.forecast_cashflow(actuals, horizon=horizon)
    try:
        mape = forecast.backtest_mape(actuals)
        st.metric("Backtest MAPE (production model)", f"{mape:.1%}",
                  help="Mean Absolute Percentage Error: train on all but the "
                       "last 6 months, forecast them, measure average % miss.")
    except ValueError:
        st.info("Not enough history to backtest.")

    with st.expander("Why is the forecast flat?"):
        st.markdown(
            "The production model forecasts the **level** (a recency-weighted "
            "average), not the wiggles — month-to-month variation here is "
            "mostly noise, and modeling noise makes forecasts *worse*. A "
            "seasonal challenger was backtested and lost; production "
            "auto-selects whichever model the evidence supports."
        )

    fig = go.Figure()
    for kind, color in (("actual", BLUE), ("forecast", AMBER)):
        sub = fc[fc["type"] == kind]
        fig.add_trace(go.Scatter(x=sub["month"], y=sub["actual"],
                                 mode="lines+markers", name=kind,
                                 line=dict(color=color)))
    fig.update_layout(title="Monthly net cash flow: actual vs. forecast")
    st.plotly_chart(style_fig(fig), use_container_width=True)

    st.subheader("Model selection (6-month holdout backtest)")
    st.caption("Champion/challenger: production auto-ships whichever model "
               "wins the backtest. A seasonal challenger was tested and "
               "**lost** — with limited history, estimating 12 monthly "
               "indices overfits noise in 10 months to capture signal in 2.")
    try:
        comp = forecast.compare_models(actuals)
        comp["mape"] = comp["mape"].map(lambda m: f"{m:.1%}")
        st.dataframe(comp, use_container_width=True, hide_index=True)
    except ValueError:
        st.info("Not enough history for model comparison.")


def page_planning() -> None:
    st.title("Monte Carlo Planning")
    live = load_live_assumptions()
    if live["source"] == "live market data":
        st.caption(f"Defaults estimated from **live {live['ticker']} history** "
                   f"({live['n_months_of_history']} months): "
                   f"return {live['annual_return_mean']:.1%}, "
                   f"vol {live['annual_return_std']:.1%}, "
                   f"inflation {live['annual_inflation']:.1%}.")
    else:
        col_warn, col_btn = st.columns([4, 1])
        col_warn.caption("Live market data temporarily unavailable (providers "
                         "rate-limit cloud IPs) — using static defaults.")
        if col_btn.button("↻ Refresh live data"):
            load_live_assumptions.clear()
            st.rerun()

    with st.expander("How does the simulation work?"):
        st.markdown(
            "10,000 possible futures: each month draws a random market return "
            "(distribution fitted to real S&P 500 history), adds your "
            "contribution, and compounds. Results are deflated to **today's "
            "dollars**, so the goal keeps its purchasing-power meaning."
        )

    d = config.SIM_DEFAULTS
    col = st.columns(3)
    contrib = col[0].number_input("Monthly contribution ($)",
                                  value=float(d["monthly_contribution"]),
                                  step=100.0)
    ret = col[1].slider("Expected annual return", 0.0, 0.15,
                        float(min(max(live["annual_return_mean"], 0.0), 0.15)),
                        0.005)
    goal = col[2].number_input("Goal ($)", value=float(d["goal"]),
                               step=10_000.0)

    res = montecarlo.simulate(
        monthly_contribution=contrib,
        annual_return_mean=ret,
        annual_return_std=live["annual_return_std"],
        annual_inflation=live["annual_inflation"],
        goal=goal,
    )
    st.metric(f"Probability of reaching {money(goal)} in {res.horizon_years} yrs",
              f"{res.prob_goal:.1%}",
              help="Share of the 10,000 simulated paths whose terminal net "
                   "worth (today's dollars) meets or exceeds the goal.")

    pct = res.percentiles()
    pc = st.columns(5)
    for i, (q, v) in enumerate(pct.items()):
        pc[i].metric(f"P{q}", money(v))

    fig = px.histogram(x=res.terminal, nbins=60,
                       title="Distribution of terminal net worth (real $)",
                       labels={"x": "Net worth ($)"})
    fig.add_vline(x=goal, line_dash="dash", line_color=RED,
                  annotation_text="Goal")
    st.plotly_chart(style_fig(fig, 420), use_container_width=True)


def page_statements() -> None:
    st.title("Statements & KPIs")
    actuals = load_actuals()
    month = actuals["month"].max()

    c1, c2 = st.columns(2)
    money_cfg = {"amount": st.column_config.NumberColumn("Amount",
                                                         format="$%.0f"),
                 "line_item": st.column_config.TextColumn("Line item")}
    with c1:
        st.subheader("Income Statement")
        st.dataframe(statements.income_statement(actuals, month),
                     use_container_width=True, hide_index=True,
                     column_config=money_cfg)
    with c2:
        st.subheader("Balance Sheet")
        st.dataframe(statements.balance_sheet(),
                     use_container_width=True, hide_index=True,
                     column_config=money_cfg)
        st.caption("The **investments** line is researched on the "
                   "*Portfolio Research* page — real SEC-filing analysis of "
                   "the companies behind it.")

    st.subheader("Key Metrics")
    k = statements.kpis(actuals, month=month)
    m = st.columns(4)
    m[0].metric("Savings Rate", f"{k['savings_rate']:.1%}",
                help="Net income ÷ income. Advisors commonly target 20%+.")
    m[1].metric("Monthly Burn", money(k["burn_rate"]),
                help="Total monthly spending across all categories.")
    m[2].metric("Runway", f"{k['runway_months']:.0f} mo",
                help="Months liquid assets (cash + investments) last at the "
                     "current burn rate if income stopped.")
    m[3].metric("Debt-to-Income", f"{k['debt_to_income']:.2f}",
                help="Total debt ÷ annual income. Lenders typically prefer "
                     "below 0.36.")


def page_company() -> None:
    st.title("Portfolio Research")
    st.caption("Your balance sheet carries an **investments** line, and the "
               "Monte Carlo plan compounds it — this page is the research "
               "desk for the companies behind that money. Fundamentals come "
               "from each company's **actual SEC filings** (10-Q/10-K via "
               "the free EDGAR API), analyzed with the same FP&A toolkit "
               "used on your own finances.")

    options = [f"{t} — {n}" for t, n in config.WATCHLIST.items()]
    options.append("Other (enter a ticker)")
    choice = st.selectbox("Company", options,
                          help="A starter watchlist of large US filers. "
                               "Pick 'Other' to research any US public ticker.")
    if choice.startswith("Other"):
        ticker = st.text_input("Ticker", value="", max_chars=6,
                               placeholder="e.g. TSLA").strip().upper()
        if not ticker:
            st.info("Enter a ticker to analyze.")
            return
    else:
        ticker = choice.split(" — ")[0]

    try:
        name, fin = load_company(ticker)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not load {ticker}: {exc}")
        return

    if fin.empty or "revenue" not in fin or fin["revenue"].dropna().empty:
        st.warning("Filings found, but revenue could not be mapped for this "
                   "company's tagging.")
        return

    rev = fin["revenue"].dropna()
    latest_q = rev.index[-1].date()
    g = edgar.qoq_yoy(fin, "revenue")
    yoy = g["yoy_growth"].iloc[-1] if not g.empty else float("nan")

    st.subheader(f"{name} — quarterly fundamentals (latest: {latest_q})")
    c1, c2, c3 = st.columns(3)
    c1.metric("Revenue (latest Q)", f"${rev.iloc[-1]/1e9:,.1f}B")
    if pd.notna(yoy):
        c2.metric("Revenue YoY", f"{yoy:+.1%}",
                  delta_color="normal" if yoy >= 0 else "inverse")
    if "net_margin" in fin and fin["net_margin"].notna().any():
        c3.metric("Net Margin (latest Q)",
                  f"{fin['net_margin'].dropna().iloc[-1]:.1%}")

    plot_df = fin.reset_index()
    fig = go.Figure()
    fig.add_trace(go.Bar(x=plot_df["quarter_end"], y=plot_df["revenue"],
                         name="Revenue", marker_color=BLUE))
    if "net_income" in fin:
        fig.add_trace(go.Scatter(x=plot_df["quarter_end"],
                                 y=plot_df["net_income"], name="Net income",
                                 mode="lines+markers",
                                 line=dict(color=AMBER)))
    fig.update_layout(title="Revenue and net income by quarter (USD)")
    st.plotly_chart(style_fig(fig), use_container_width=True)

    margin_cols = [c for c in ("gross_margin", "operating_margin",
                               "net_margin") if c in fin]
    if margin_cols:
        mfig = px.line(plot_df, x="quarter_end", y=margin_cols, markers=True,
                       title="Margin trend")
        mfig.update_layout(yaxis_tickformat=".0%")
        st.plotly_chart(style_fig(mfig), use_container_width=True)

    st.subheader("Growth analysis (QoQ / YoY)")
    gt = g.copy()
    gt.index = gt.index.date
    gt["revenue"] = gt["revenue"].map(lambda v: f"${v/1e9:,.2f}B")
    for col_ in ("qoq_growth", "yoy_growth"):
        gt[col_] = gt[col_].map(lambda v: f"{v:+.1%}" if pd.notna(v) else "—")
    st.dataframe(gt.tail(8), use_container_width=True)

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
        st.metric("Backtest MAPE (last 4 quarters held out)", f"{mape_q:.1%}")

        ffig = go.Figure()
        ffig.add_trace(go.Scatter(x=rev_q.index.astype(str), y=rev_q.values,
                                  name="actual", mode="lines+markers",
                                  line=dict(color=BLUE)))
        ffig.add_trace(go.Scatter(x=fc_q.index.astype(str), y=fc_q.values,
                                  name="forecast", mode="lines+markers",
                                  line=dict(color=AMBER, dash="dot")))
        ffig.update_layout(title="Quarterly revenue: actual vs. forecast")
        st.plotly_chart(style_fig(ffig), use_container_width=True)
    else:
        st.info("Not enough quarterly history to forecast.")

    st.caption("Source: SEC EDGAR company facts (10-Q/10-K filings). Q4 "
               "derived as FY minus reported quarters where not filed "
               "directly.")
    with st.expander("How are the filings parsed?"):
        st.markdown(
            "Companies tag identical concepts differently in XBRL "
            "(`Revenues` vs `RevenueFromContractWithCustomer...`), so each "
            "concept tries an ordered list of candidate tags. And because "
            "companies file a full-year 10-K rather than a Q4 statement, "
            "**Q4 = FY − (Q1+Q2+Q3)** is derived automatically. Parsing is "
            "unit-tested against a controlled payload."
        )


# ===========================================================================
# App shell
# ===========================================================================

st.set_page_config(page_title="FinScope — Personal FP&A", page_icon="📊",
                   layout="wide")
st.markdown(CSS, unsafe_allow_html=True)

pages = {
    "": [st.Page(page_overview, title="Overview", icon="🏠", default=True)],
    "Personal FP&A": [
        st.Page(page_variance, title="Budget vs. Actual", icon="📉"),
        st.Page(page_forecast, title="Rolling Forecast", icon="📈"),
        st.Page(page_planning, title="Monte Carlo Planning", icon="🎲"),
        st.Page(page_statements, title="Statements & KPIs", icon="📑"),
    ],
    "Investments": [
        st.Page(page_company, title="Portfolio Research", icon="🏢"),
    ],
}

nav = st.navigation(pages)

with st.sidebar:
    st.markdown("---")
    st.caption("**FinScope** · personal FP&A platform\n\n"
               "[Source on GitHub](https://github.com/anichan2004/finscope)")

nav.run()
