from finscope import montecarlo


def test_prob_between_zero_and_one():
    res = montecarlo.simulate(n_simulations=2000, seed=3)
    assert 0.0 <= res.prob_goal <= 1.0


def test_higher_contribution_raises_prob():
    low = montecarlo.simulate(monthly_contribution=500, n_simulations=4000, seed=5)
    high = montecarlo.simulate(monthly_contribution=2500, n_simulations=4000, seed=5)
    assert high.prob_goal >= low.prob_goal


def test_percentiles_monotonic():
    res = montecarlo.simulate(n_simulations=3000, seed=9)
    p = res.percentiles()
    assert p[10] <= p[50] <= p[90]
