"""EDGAR parsing tests using a synthetic company-facts payload.

The fetch functions hit the network; the parsing is pure. Testing the
parsing against a controlled payload proves the tricky logic (tag fallback,
Q4 derivation from the 10-K) without depending on the SEC being reachable.
"""
import pandas as pd

from finscope import edgar


def _facts():
    """Minimal companyfacts payload: 3 quarters + a 10-K annual figure,
    using the *second* candidate revenue tag to exercise the fallback."""
    def q(start, end, val):
        return {"start": start, "end": end, "val": val, "form": "10-Q"}

    return {
        "entityName": "TestCo",
        "facts": {"us-gaap": {
            "Revenues": {"units": {"USD": [
                q("2024-01-01", "2024-03-31", 100.0),
                q("2024-04-01", "2024-06-30", 110.0),
                q("2024-07-01", "2024-09-30", 120.0),
                {"start": "2024-01-01", "end": "2024-12-31",
                 "val": 470.0, "form": "10-K"},
            ]}},
            "NetIncomeLoss": {"units": {"USD": [
                q("2024-01-01", "2024-03-31", 10.0),
                q("2024-04-01", "2024-06-30", 11.0),
                q("2024-07-01", "2024-09-30", 12.0),
                {"start": "2024-01-01", "end": "2024-12-31",
                 "val": 47.0, "form": "10-K"},
            ]}},
            "Assets": {"units": {"USD": [
                {"end": "2024-03-31", "val": 1000.0},
                {"end": "2024-06-30", "val": 1050.0},
            ]}},
        }},
    }


def test_tag_fallback_and_q4_derivation():
    s = edgar.extract_quarterly(_facts(), edgar.TAGS["revenue"])
    # 3 reported quarters + derived Q4
    assert len(s) == 4
    # Q4 = 470 - (100 + 110 + 120) = 140
    assert s[pd.Timestamp("2024-12-31")] == 140.0


def test_instant_extraction():
    s = edgar.extract_instant(_facts(), edgar.INSTANT_TAGS["total_assets"])
    assert len(s) == 2
    assert s.iloc[-1] == 1050.0


def test_build_financials_margins():
    df = edgar.build_financials(_facts())
    assert "net_margin" in df.columns
    # Q1 margin = 10 / 100
    assert abs(df["net_margin"].iloc[0] - 0.10) < 1e-9


def test_qoq_yoy_growth():
    df = edgar.build_financials(_facts())
    g = edgar.qoq_yoy(df, "revenue")
    # Q2 QoQ = 110/100 - 1 = 10%
    assert abs(g["qoq_growth"].iloc[1] - 0.10) < 1e-9
