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
    assert len(comp) == 4
    assert comp["mape"].is_monotonic_increasing


def test_bakeoff_includes_seasonal_challenger(actuals):
    comp = forecast.compare_models(actuals)
    assert len(comp) == 4
    assert "Seasonal exp smoothing" in set(comp["model"])


def test_seasonal_indices_normalized(actuals):
    series = forecast._monthly_net_series(actuals)
    idx = forecast._seasonal_indices(series)
    assert len(idx) == 12
    assert abs(sum(idx.values()) / 12 - 1.0) < 1e-9


def test_auto_selects_and_forecasts(actuals):
    fc = forecast.forecast_cashflow(actuals, horizon=6, method="auto")
    assert (fc["type"] == "forecast").sum() == 6
