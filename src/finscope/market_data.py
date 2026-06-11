"""Pull REAL market and macro data to ground the planning model.

Two live sources, both free:
  * Equity returns  -> yfinance (S&P 500), with a keyless Stooq fallback.
  * Inflation (CPI)  -> FRED API (needs a free key); falls back to a default.

The point of this module is that the Monte Carlo engine no longer runs on
made-up assumptions: the expected return and volatility are estimated from
*actual* historical market data, and the goal is discounted with *actual*
inflation. If every network path fails, we degrade gracefully to the static
assumptions in config so the app still runs offline.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from . import config


def fetch_market_returns(
    ticker: str = "^GSPC", start: str = "2005-01-01"
) -> pd.Series:
    """Monthly total returns for an index/ticker.

    Tries yfinance first, then Stooq (no API key). Returns a Series of monthly
    simple returns indexed by month-end.
    """
    # --- attempt 1: yfinance --------------------------------------------
    try:
        import yfinance as yf

        raw = yf.download(
            ticker, start=start, interval="1mo",
            auto_adjust=True, progress=False,
        )
        if raw is not None and not raw.empty:
            close = raw["Close"]
            if isinstance(close, pd.DataFrame):  # multiindex guard
                close = close.iloc[:, 0]
            returns = close.pct_change().dropna()
            returns.name = "monthly_return"
            return returns
    except Exception as exc:  # noqa: BLE001
        warnings.warn(f"yfinance failed ({exc}); trying Stooq fallback.")

    # --- attempt 2: Stooq via pandas-datareader -------------------------
    try:
        from pandas_datareader import data as pdr

        symbol = "^SPX" if ticker in ("^GSPC", "SPY") else ticker
        raw = pdr.DataReader(symbol, "stooq", start=start)
        close = raw["Close"].sort_index()
        monthly = close.resample("ME").last()
        returns = monthly.pct_change().dropna()
        returns.name = "monthly_return"
        return returns
    except Exception as exc:  # noqa: BLE001
        warnings.warn(f"Stooq fallback failed ({exc}); using config defaults.")
        return pd.Series(dtype=float, name="monthly_return")


def annualized_stats(monthly_returns: pd.Series) -> tuple[float, float]:
    """Annualized mean and volatility from monthly simple returns."""
    if monthly_returns.empty:
        return config.SIM_DEFAULTS["annual_return_mean"], config.SIM_DEFAULTS["annual_return_std"]
    mean_a = float(monthly_returns.mean()) * 12.0
    std_a = float(monthly_returns.std()) * np.sqrt(12.0)
    return mean_a, std_a


def fetch_inflation(fred_api_key: str | None = None) -> float:
    """Latest year-over-year CPI inflation from FRED (series CPIAUCSL).

    Without a key, returns the config default. Get a free key at
    https://fred.stlouisfed.org/docs/api/api_key.html
    """
    if not fred_api_key:
        return config.SIM_DEFAULTS["annual_inflation"]
    try:
        from fredapi import Fred

        fred = Fred(api_key=fred_api_key)
        cpi = fred.get_series("CPIAUCSL").dropna()
        yoy = cpi.iloc[-1] / cpi.iloc[-13] - 1.0  # 12-month change
        return float(yoy)
    except Exception as exc:  # noqa: BLE001
        warnings.warn(f"FRED fetch failed ({exc}); using default inflation.")
        return config.SIM_DEFAULTS["annual_inflation"]


def derive_assumptions(
    ticker: str = "^GSPC",
    start: str = "2005-01-01",
    fred_api_key: str | None = None,
) -> dict:
    """Bundle live-data-derived assumptions ready for montecarlo.simulate()."""
    returns = fetch_market_returns(ticker, start)
    mean_a, std_a = annualized_stats(returns)
    inflation = fetch_inflation(fred_api_key)

    source = "live market data" if not returns.empty else "config defaults"
    return {
        "annual_return_mean": round(mean_a, 4),
        "annual_return_std": round(std_a, 4),
        "annual_inflation": round(inflation, 4),
        "n_months_of_history": int(len(returns)),
        "source": source,
        "ticker": ticker,
    }


if __name__ == "__main__":
    a = derive_assumptions()
    print("Live-derived assumptions:")
    for k, v in a.items():
        print(f"  {k}: {v}")
