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


def _seasonal_indices(series: pd.Series) -> dict[int, float]:
    """Month-of-year seasonal indices: each month's average relative to the
    overall average, normalized so the indices mean 1.0. December at 0.85
    means December typically runs 15% below a normal month."""
    df = pd.DataFrame({"v": series.to_numpy(dtype=float),
                       "m": [p.month for p in series.index]})
    overall = df["v"].mean()
    if overall == 0:
        return {m: 1.0 for m in range(1, 13)}
    idx = (df.groupby("m")["v"].mean() / overall).to_dict()
    # months absent from history default to neutral
    full = {m: float(idx.get(m, 1.0)) for m in range(1, 13)}
    norm = sum(full.values()) / 12.0
    return {m: v / norm for m, v in full.items()}


def seasonal_exp_smoothing_forecast(
    series: pd.Series, horizon: int = 12, alpha: float = 0.4
) -> pd.Series:
    """Exponential smoothing with multiplicative month-of-year seasonality.

    Deseasonalize history, smooth the level, then reapply each future
    month's seasonal factor. Captures repeating patterns (e.g. a year-end
    spending spike) that a flat level forecast deliberately ignores.
    """
    indices = _seasonal_indices(series)
    deseason = pd.Series(
        [v / indices[p.month] for p, v in series.items()], index=series.index
    )
    level_fc = exp_smoothing_forecast(deseason, horizon=horizon, alpha=alpha)
    out = pd.Series(
        [lvl * indices[p.month] for p, lvl in level_fc.items()],
        index=level_fc.index, name="forecast",
    )
    return out


def forecast_cashflow(
    actuals: pd.DataFrame, horizon: int = 12, alpha: float = 0.4,
    method: str = "auto",
) -> pd.DataFrame:
    """Forecast net cash flow. method='auto' runs the model bake-off on a
    holdout and ships the champion -- challenger models (like seasonal) only
    take over production when they actually beat the incumbent."""
    series = _monthly_net_series(actuals)

    if method == "auto":
        try:
            champion = compare_models(actuals).iloc[0]["model"]
        except ValueError:
            champion = "Exponential smoothing"
        method = "seasonal" if champion == "Seasonal exp smoothing" else "plain"

    if method == "seasonal" and len(series) >= 18:
        fc = seasonal_exp_smoothing_forecast(series, horizon=horizon, alpha=alpha)
    else:
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

    seas = seasonal_exp_smoothing_forecast(train, horizon=holdout)
    results.append(("Seasonal exp smoothing", _mape(actual, seas.to_numpy(dtype=float))))

    df = pd.DataFrame(results, columns=["model", "mape"]).sort_values("mape")
    df["mape"] = df["mape"].round(4)
    return df.reset_index(drop=True)
