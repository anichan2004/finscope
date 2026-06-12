"""Print a "memo data pack": every figure the analysis memo needs, in order.

Run in Colab (or anywhere with internet):

    PYTHONPATH=src python -m scripts.memo_data AAPL

Reuses the same EDGAR mapping and forecast engine as the dashboard, so the
memo's numbers are exactly what FinScope reports.
"""
from __future__ import annotations

import sys

import pandas as pd

from finscope import edgar, forecast


def main(ticker: str = "AAPL") -> None:
    name, fin = edgar.get_company_financials(ticker, quarters=16)
    if fin.empty or fin["revenue"].dropna().empty:
        print(f"No mappable revenue for {ticker}")
        return

    rev = fin["revenue"].dropna()
    g = edgar.qoq_yoy(fin, "revenue")

    print("=" * 70)
    print(f"MEMO DATA PACK — {name} ({ticker.upper()})")
    print(f"Latest filed quarter end: {rev.index[-1].date()}")
    print("=" * 70)

    print("\n[SECTION 2] Quarterly revenue, QoQ, YoY (last 8 quarters):")
    t = g.tail(8).copy()
    t.index = t.index.date
    t["revenue"] = t["revenue"].map(lambda v: f"${v/1e9:,.2f}B")
    for c in ("qoq_growth", "yoy_growth"):
        t[c] = t[c].map(lambda v: f"{v:+.1%}" if pd.notna(v) else "—")
    print(t.to_string())

    print("\n[SECTION 3] Margins (last 8 quarters):")
    mcols = [c for c in ("gross_margin", "operating_margin", "net_margin")
             if c in fin]
    m = (fin[mcols].dropna(how="all").tail(8) * 100).round(1)
    m.index = m.index.date
    print(m.to_string())

    print("\n[SECTION 4] Revenue forecast (next 4 quarters) + backtest:")
    rev_q = rev.copy()
    rev_q.index = pd.PeriodIndex(rev_q.index, freq="Q")
    fc = forecast.exp_smoothing_forecast(rev_q, horizon=4, freq="Q")
    for p, v in fc.items():
        print(f"  {p}: ${v/1e9:,.2f}B")
    hold = 4
    train, test = rev_q.iloc[:-hold], rev_q.iloc[-hold:]
    pred = forecast.exp_smoothing_forecast(train, horizon=hold, freq="Q")
    mape = forecast._mape(test.to_numpy(dtype=float),
                          pred.to_numpy(dtype=float))
    print(f"  Backtest MAPE (last {hold} quarters held out): {mape:.1%}")

    print("\n[HEADLINES] for the executive summary:")
    yoy = g["yoy_growth"].iloc[-1]
    print(f"  Latest-Q revenue: ${rev.iloc[-1]/1e9:,.1f}B")
    if pd.notna(yoy):
        print(f"  Revenue YoY: {yoy:+.1%}")
    if "net_margin" in fin and fin["net_margin"].notna().any():
        nm = fin["net_margin"].dropna()
        print(f"  Net margin: {nm.iloc[-1]:.1%} "
              f"(4 quarters ago: {nm.iloc[-5]:.1%})" if len(nm) >= 5
              else f"  Net margin: {nm.iloc[-1]:.1%}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "AAPL")
