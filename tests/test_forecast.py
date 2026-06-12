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


def test_compare_models_ranks_by_mape(actuals):
    comp = forecast.compare_models(actuals)
    assert set(comp.columns) == {"model", "mape"}
    assert len(comp) == 3
    assert comp["mape"].is_monotonic_increasing
