import pandas as pd

from finscope import forecast


def test_forecast_extends_horizon(actuals):
    fc = forecast.forecast_cashflow(actuals, horizon=12)
    assert (fc["type"] == "forecast").sum() == 12
    assert (fc["type"] == "actual").sum() >= 12


def test_mape_is_fraction(actuals):
    mape = forecast.backtest_mape(actuals, holdout=6)
    assert mape >= 0.0
    assert mape == mape  # not NaN
