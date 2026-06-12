"""Real corporate financials from SEC EDGAR.

EDGAR is the SEC's public filing system: every US public company's financial
statements, free, no API key. This module turns that raw feed into clean
quarterly financials an analyst can work with.

The hard (and interesting) part is the mapping. Companies tag the same
concept with different XBRL tags ("Revenues" vs
"RevenueFromContractWithCustomerExcludingAssessedTax"), and Q4 income-
statement figures are usually NOT reported directly -- the 10-K reports the
full year, so Q4 must be derived as FY minus the three reported quarters.
Handling both correctly is exactly the kind of data wrangling a real FP&A /
equity analyst does.

SEC fair-access policy requires a User-Agent identifying the caller:
set EDGAR_USER_AGENT (e.g. "FinScope your.email@example.com").
"""
from __future__ import annotations

import os
import warnings

import pandas as pd
import requests

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

# Candidate XBRL tags per concept, in preference order. First tag with
# usable data wins. This list covers the large majority of US filers.
TAGS = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
    ],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "operating_income": ["OperatingIncomeLoss"],
    "gross_profit": ["GrossProfit"],
}

# Balance-sheet concepts are point-in-time ("instant"), not duration.
INSTANT_TAGS = {
    "total_assets": ["Assets"],
    "total_liabilities": ["Liabilities"],
    "equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "cash": ["CashAndCashEquivalentsAtCarryingValue"],
}


def _headers() -> dict:
    ua = os.environ.get("EDGAR_USER_AGENT", "FinScope research contact@example.com")
    return {"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}


def get_cik(ticker: str) -> int:
    """Resolve a ticker symbol to the SEC's CIK identifier."""
    resp = requests.get(TICKER_MAP_URL, headers=_headers(), timeout=30)
    resp.raise_for_status()
    for entry in resp.json().values():
        if entry["ticker"].upper() == ticker.upper():
            return int(entry["cik_str"])
    raise ValueError(f"Ticker '{ticker}' not found in SEC registry")


def fetch_company_facts(cik: int) -> dict:
    """Download the full XBRL company-facts payload for a CIK."""
    resp = requests.get(FACTS_URL.format(cik=cik), headers=_headers(), timeout=60)
    resp.raise_for_status()
    return resp.json()


# --------------------------------------------------------------------------
# Parsing -- pure functions, unit-testable without the network
# --------------------------------------------------------------------------

def _entries(facts: dict, tag: str) -> list[dict]:
    try:
        return facts["facts"]["us-gaap"][tag]["units"]["USD"]
    except KeyError:
        return []


def _duration_days(item: dict) -> float:
    try:
        return (pd.Timestamp(item["end"]) - pd.Timestamp(item["start"])).days
    except (KeyError, ValueError):
        return float("nan")


def extract_quarterly(facts: dict, tag_candidates: list[str]) -> pd.Series:
    """Quarterly values for a duration concept, with Q4 derived from the 10-K.

    Direct quarterly figures have a ~3 month duration (70-100 days). Annual
    figures (~350-375 days) come from the 10-K; for each one we derive
    Q4 = FY - (Q1 + Q2 + Q3) when exactly three quarters fall inside that
    fiscal year. Indexed by quarter-end date.
    """
    for tag in tag_candidates:
        items = _entries(facts, tag)
        if not items:
            continue

        quarterly: dict[pd.Timestamp, float] = {}
        annual: list[dict] = []
        for it in items:
            if "val" not in it or "end" not in it or "start" not in it:
                continue
            d = _duration_days(it)
            end = pd.Timestamp(it["end"])
            if 70 <= d <= 100:
                quarterly[end] = float(it["val"])  # later filings overwrite
            elif 350 <= d <= 375:
                annual.append(it)

        # Derive missing Q4s from annual totals
        for it in annual:
            fy_start, fy_end = pd.Timestamp(it["start"]), pd.Timestamp(it["end"])
            if fy_end in quarterly:
                continue
            inside = [v for e, v in quarterly.items() if fy_start < e < fy_end]
            if len(inside) == 3:
                quarterly[fy_end] = float(it["val"]) - sum(inside)

        if quarterly:
            s = pd.Series(quarterly).sort_index()
            s.index.name = "quarter_end"
            return s

    return pd.Series(dtype=float)


def extract_instant(facts: dict, tag_candidates: list[str]) -> pd.Series:
    """Point-in-time values (balance-sheet items), indexed by date."""
    for tag in tag_candidates:
        items = _entries(facts, tag)
        if not items:
            continue
        vals = {pd.Timestamp(it["end"]): float(it["val"])
                for it in items if "val" in it and "end" in it}
        if vals:
            s = pd.Series(vals).sort_index()
            s.index.name = "quarter_end"
            return s
    return pd.Series(dtype=float)


def build_financials(facts: dict, quarters: int = 16) -> pd.DataFrame:
    """Assemble a clean quarterly financials table from raw company facts."""
    cols = {}
    for name, tags in TAGS.items():
        cols[name] = extract_quarterly(facts, tags)
    for name, tags in INSTANT_TAGS.items():
        cols[name] = extract_instant(facts, tags)

    df = pd.DataFrame(cols).sort_index()
    df = df[df["revenue"].notna()] if "revenue" in df and df["revenue"].notna().any() else df
    df = df.tail(quarters)

    if "revenue" in df:
        if "net_income" in df:
            df["net_margin"] = df["net_income"] / df["revenue"]
        if "operating_income" in df:
            df["operating_margin"] = df["operating_income"] / df["revenue"]
        if "gross_profit" in df:
            df["gross_margin"] = df["gross_profit"] / df["revenue"]
    return df


def qoq_yoy(df: pd.DataFrame, metric: str = "revenue") -> pd.DataFrame:
    """Quarter-over-quarter and year-over-year growth -- the variance view
    an analyst runs every earnings cycle."""
    if metric not in df or df[metric].dropna().empty:
        return pd.DataFrame()
    out = df[[metric]].dropna().copy()
    out["qoq_growth"] = out[metric].pct_change()
    out["yoy_growth"] = out[metric].pct_change(4)
    return out


def get_company_financials(ticker: str, quarters: int = 16) -> tuple[str, pd.DataFrame]:
    """Convenience wrapper: ticker -> (company name, quarterly financials)."""
    cik = get_cik(ticker)
    facts = fetch_company_facts(cik)
    name = facts.get("entityName", ticker.upper())
    df = build_financials(facts, quarters=quarters)
    if df.empty:
        warnings.warn(f"No mappable quarterly data found for {ticker}")
    return name, df
