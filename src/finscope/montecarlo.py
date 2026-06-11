"""Monte Carlo net-worth projection.

Simulates many possible paths of net worth under uncertain monthly returns,
then reports the distribution of outcomes and the probability of hitting a
goal. Returns are drawn monthly from a normal distribution implied by the
annual mean/vol; contributions are made each month; results are reported in
real (inflation-adjusted) terms.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import config


@dataclass
class SimResult:
    paths: np.ndarray            # shape (n_sims, months + 1), real dollars
    goal: float
    horizon_years: int

    @property
    def terminal(self) -> np.ndarray:
        return self.paths[:, -1]

    @property
    def prob_goal(self) -> float:
        return float((self.terminal >= self.goal).mean())

    def percentiles(self, qs=(10, 25, 50, 75, 90)) -> dict[int, float]:
        return {q: float(np.percentile(self.terminal, q)) for q in qs}


def simulate(
    starting_net_worth: float | None = None,
    monthly_contribution: float | None = None,
    annual_return_mean: float | None = None,
    annual_return_std: float | None = None,
    annual_inflation: float | None = None,
    horizon_years: int | None = None,
    goal: float | None = None,
    n_simulations: int | None = None,
    seed: int = 7,
) -> SimResult:
    d = config.SIM_DEFAULTS
    start = starting_net_worth if starting_net_worth is not None else d["starting_net_worth"]
    contrib = monthly_contribution if monthly_contribution is not None else d["monthly_contribution"]
    mu_a = annual_return_mean if annual_return_mean is not None else d["annual_return_mean"]
    sd_a = annual_return_std if annual_return_std is not None else d["annual_return_std"]
    infl = annual_inflation if annual_inflation is not None else d["annual_inflation"]
    years = horizon_years if horizon_years is not None else d["horizon_years"]
    goal = goal if goal is not None else d["goal"]
    n = n_simulations if n_simulations is not None else d["n_simulations"]

    rng = np.random.default_rng(seed)
    months = years * 12
    mu_m = mu_a / 12.0
    sd_m = sd_a / np.sqrt(12.0)
    infl_m = infl / 12.0

    paths = np.empty((n, months + 1), dtype=float)
    paths[:, 0] = start
    for t in range(1, months + 1):
        r = rng.normal(mu_m, sd_m, size=n)
        paths[:, t] = paths[:, t - 1] * (1.0 + r) + contrib

    # deflate to today's dollars so the goal is interpreted in real terms
    deflator = (1.0 + infl_m) ** np.arange(months + 1)
    paths = paths / deflator

    return SimResult(paths=paths, goal=goal, horizon_years=years)
