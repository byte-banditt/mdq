import numpy as np
import pytest
from indexkit.data import config
from indexkit.structured import autocallable, factors, greeks, payoff, skew_prices


def test_deterministic_autocall():
    quote = autocallable(100, 100, 0, 0, 0, [0.25, 0.5, 0.75, 1], paths=1000)
    assert quote["price"] == pytest.approx(1.02)
    assert quote["early_call_prob"] == [1.0, 0.0, 0.0, 0.0]
    assert quote["capital_loss_prob"] == 0


def test_loss_payoff():
    obs = np.array([[0.8, 0.9], [0.5, 0.8]])
    minimum = np.array([0.4, 0.7])
    times = np.array([0.5, 1.0])
    result = payoff(100, 100, obs, minimum, times, 0, 0.08, 1, 0.6)
    assert result["price"] == pytest.approx((0.58 + 1.08) / 2)
    assert result["capital_loss_prob"] == 0.5


def test_crn_and_probability():
    p = config()["structured"]
    obs, a, t = factors(p["vol"], p["rate"], p["q"], p["observations"], 10000, 42)
    obs2, a2, t2 = factors(p["vol"], p["rate"], p["q"], p["observations"], 10000, 42)
    np.testing.assert_array_equal(obs, obs2)
    q = payoff(1000, 1000, obs, a, t, 0.05, 0.08, 1, 0.6)
    assert 0 <= sum(q["early_call_prob"]) <= 1
    assert 0 <= q["capital_loss_prob"] <= 1 - sum(q["early_call_prob"]) + 1e-12
    g = greeks(p, paths=10000)
    assert all(np.isfinite(x) for x in g.values())
    skew = skew_prices(config()["options"])
    assert (skew.illustrative_vol.diff().dropna() < 0).all()
    assert np.isfinite(skew.to_numpy()).all()
