# FinScope — A Personal FP&A Platform
[![Live Demo](https://img.shields.io/badge/Live%20Demo-Streamlit-FF4B4B?logo=streamlit)](YOUR_STREAMLIT_URL)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/anichan2004/finscope/blob/main/notebooks/finscope_colab.ipynb)
[![CI](https://github.com/anichan2004/finscope/actions/workflows/ci.yml/badge.svg)](https://github.com/anichan2004/finscope/actions/workflows/ci.yml)

**[▶ Try the live dashboard](https://finscope-p5urvdzp2du7ulmumu3jeq.streamlit.app/)** · built with Python, SQL, and live market data.

<img width="1917" height="968" alt="image" src="https://github.com/user-attachments/assets/3d74118f-dec0-494c-9045-188dad656e52" />


FinScope applies the methods a corporate **Financial Planning & Analysis (FP&A)** team
uses to run a business — budget-vs-actual variance analysis, rolling forecasts,
scenario simulation, and financial-statement reporting — to personal finances.

It is built to demonstrate the toolkit of a financial analyst: **Python, SQL,
financial modeling, forecasting, and dashboarding**, with tests and CI on top.

### Data sources

| Layer | Source | Live? |
|---|---|---|
| Transactions | Synthetic generator | No — personal bank data is private. Production uses **Plaid** (consent-based bank aggregation). |
| Market returns | S&P 500 via **yfinance** (Stooq fallback) | **Yes** — drives the Monte Carlo off real return & volatility |
| Inflation | **FRED** CPI (free API key) | **Yes** — goal is discounted with live macro data |

No real personal financial information is ever committed. The planning model runs on
**live market data**; the transaction layer is synthetic-but-clearly-labeled, with
Plaid documented as the real-data path (see *Extensions*).

---

## What it does

| Module | FP&A concept | Where |
|---|---|---|
| Budget vs. Actual variance | The core monthly variance report (favorable / unfavorable, $ and %) | `variance.py` |
| Rolling cash-flow forecast | Exponential-smoothing forecast with a **MAPE backtest** | `forecast.py` |
| Monte Carlo planning | 10,000-path net-worth simulation → probability of hitting a goal (in real $) | `montecarlo.py` |
| Live market + macro data | Real S&P 500 returns & FRED inflation feeding the simulation | `market_data.py` |
| Personal 3-statement view | Income statement, balance sheet, KPIs (savings rate, runway, DTI) | `statements.py` |
| SQL aggregation | Monthly rollups done in SQL on a SQLite store | `database.py` |
| Excel automation | Formatted, color-coded variance workbook via openpyxl | `excel_report.py` |
| Dashboard | Interactive Streamlit app over all of the above | `app/streamlit_app.py` |

---

## Quick start

```bash
pip install -r requirements.txt

# 1. generate synthetic data, categorize, load to SQLite, emit an Excel report
python -m scripts.setup_data

# 2. launch the dashboard
streamlit run app/streamlit_app.py

# run the tests
pytest -q
```

`setup_data` prints headline numbers, e.g.:

```
rule-based categorization accuracy: 98.0%
forecast backtest MAPE: 6.7%
```

### Run in Google Colab

Open `notebooks/finscope_colab.ipynb` in Colab, set your GitHub username in the
clone cell, and run top to bottom. It pulls **live market data**, runs the full
analysis, and renders every chart inline. (A FRED key is optional — paste it when
prompted for live inflation; market returns are live either way.)

---

## Methodology notes

**Variance convention.** For expense categories, variance = `budget − actual`, so a
positive variance is *favorable* (you spent less than planned). This matches how a
real variance report reads.

**Forecasting.** Net monthly cash flow is projected with simple exponential
smoothing. The choice is deliberate — it is explainable and the backtest (train on
all but the last *n* months, score MAPE on the holdout) is the same accuracy check
an FP&A team runs on its rolling forecast.

**Monte Carlo.** Monthly returns are drawn from a normal distribution implied by the
annual mean/volatility; contributions are added each month; terminal values are
deflated to today's dollars so the goal is interpreted in **real** terms. The output
is the full distribution plus the probability of reaching the goal.

---

## Project structure

```
finscope/
├── src/finscope/        # the engine (importable package)
│   ├── config.py        # categories, budgets, assumptions
│   ├── data_generator.py
│   ├── categorize.py
│   ├── database.py
│   ├── variance.py
│   ├── forecast.py
│   ├── montecarlo.py
│   ├── statements.py
│   └── excel_report.py
├── app/streamlit_app.py # dashboard
├── scripts/setup_data.py
├── tests/               # pytest suite
└── .github/workflows/   # CI
```

## Tech stack

Python · pandas · numpy · SQL (SQLite) · openpyxl · Streamlit · Plotly · pytest · GitHub Actions

---

## Possible extensions

- **Real transactions via Plaid.** Swap the synthetic generator for Plaid's
  `/transactions/get` endpoint (free sandbox, then development with your own linked
  bank). The rest of the pipeline is source-agnostic — it only needs `date`,
  `description`, `category`, `amount` columns.
- Swap rule-based categorization for a trained classifier and compare accuracy.
- Add Postgres as a drop-in backend (the schema is written to port cleanly).
- Layer seasonality into the forecast and compare MAPE.
- Deploy the dashboard to Streamlit Community Cloud for a live demo link.
