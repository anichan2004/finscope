"""Rolling cash-flow forecast with a backtest.

Deliberately uses simple, explainable methods (exponential smoothing with an
optional seasonal lift) rather than a heavyweight model. The backtest reports
MAPE on a holdout, which is exactly the accuracy metric an FP&A team tracks on
its rolling forecast.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def _monthly_net_series(actuals: pd.DataFrame) -> pd.Series:
    """Net cash flow per month (income minus expenses) as a time series."""
    s = (
        actuals.groupby("month")["net_amount"].sum().sort_index()
    )
    s.index = pd.PeriodIndex(s.index, freq="M")
    return s


def exp_smoothing_forecast(
    series: pd.Series, horizon: int = 12, alpha: float = 0.4, freq: str = "M"
) -> pd.Series:
    """Simple exponential smoothing; flat forward projection of the level."""
    values = series.to_numpy(dtype=float)
    level = values[0]
    for v in values[1:]:
        level = alpha * v + (1 - alpha) * level

    last_period = series.index[-1]
    future_index = pd.period_range(last_period + 1, periods=horizon, freq=freq)
    return pd.Series([level] * horizon, index=future_index, name="forecast")


def forecast_cashflow(
    actuals: pd.DataFrame, horizon: int = 12, alpha: float = 0.4
) -> pd.DataFrame:
    series = _monthly_net_series(actuals)
    fc = exp_smoothing_forecast(series, horizon=horizon, alpha=alpha)
    hist = series.rename("actual").to_frame()
    hist["type"] = "actual"
    fut = fc.rename("actual").to_frame()
    fut["type"] = "forecast"
    out = pd.concat([hist, fut])
    out.index = out.index.astype(str)
    return out.reset_index(names="month")


def backtest_mape(
    actuals: pd.DataFrame, holdout: int = 6, alpha: float = 0.4
) -> float:
    """Train on all but the last `holdout` months, score MAPE on them."""
    series = _monthly_net_series(actuals)
    if len(series) <= holdout + 2:
        raise ValueError("Not enough history to backtest")

    train, test = series.iloc[:-holdout], series.iloc[-holdout:]
    fc = exp_smoothing_forecast(train, horizon=holdout, alpha=alpha)
    return _mape(test.to_numpy(dtype=float), fc.to_numpy(dtype=float))


def _mape(actual: np.ndarray, pred: np.ndarray) -> float:
    denom = np.where(np.abs(actual) < 1e-6, np.nan, np.abs(actual))
    return float(np.nanmean(np.abs((actual - pred) / denom)))


def compare_models(actuals: pd.DataFrame, holdout: int = 6) -> pd.DataFrame:
    """Backtest several candidate models and rank them by MAPE.

    Models:
      * Naive (last value carried forward) -- the baseline any model must beat
      * 3-month moving average
      * Exponential smoothing (the production model)

    Showing the comparison is the point: model choice should be evidenced,
    not assumed.
    """
    series = _monthly_net_series(actuals)
    if len(series) <= holdout + 3:
        raise ValueError("Not enough history to backtest")

    train, test = series.iloc[:-holdout], series.iloc[-holdout:]
    actual = test.to_numpy(dtype=float)

    results = []

    naive_pred = np.full(holdout, float(train.iloc[-1]))
    results.append(("Naive (last value)", _mape(actual, naive_pred)))

    ma_pred = np.full(holdout, float(train.iloc[-3:].mean()))
    results.append(("3-month moving average", _mape(actual, ma_pred)))

    es = exp_smoothing_forecast(train, horizon=holdout)
    results.append(("Exponential smoothing", _mape(actual, es.to_numpy(dtype=float))))

    df = pd.DataFrame(results, columns=["model", "mape"]).sort_values("mape")
    df["mape"] = df["mape"].round(4)
    return df.reset_index(drop=True)
