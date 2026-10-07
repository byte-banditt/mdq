import numpy as np
import pytest
from indexkit.data import config
from indexkit.options import digital, implied_vol, monte_carlo, sensitivity, vanilla


@pytest.mark.parametrize("kind", ["call", "put"])
def test_greeks(kind):
    s, k, t, r, v, q = 103.0, 100.0, 0.7, 0.04, 0.23, 0.015
    value = lambda spot=s, time=t, rate=r, vol=v: float(
        vanilla(spot, k, time, rate, vol, q, kind)["price"]
    )
    g = vanilla(s, k, t, r, v, q, kind)
    hs = 0.01
    h = 1e-5
    assert g["delta"] == pytest.approx(
        (value(spot=s + hs) - value(spot=s - hs)) / (2 * hs), rel=1e-6
    )
    assert g["gamma"] == pytest.approx(
        (value(spot=s + hs) - 2 * value() + value(spot=s - hs)) / hs**2, rel=1e-5
    )
    for field, arg in [("vega", "vol"), ("rho", "rate"), ("theta", "time")]:
        base = {"vol": v, "rate": r, "time": t}[arg]
        diff = (value(**{arg: base + h}) - value(**{arg: base - h})) / (2 * h)
        assert g[field] == pytest.approx(-diff if field == "theta" else diff, rel=1e-6)
    d = digital(s, k, t, r, v, q, kind)
    fn = lambda spot=s, vol=v: float(digital(spot, k, t, r, vol, q, kind)["price"])
    assert d["delta"] == pytest.approx((fn(spot=s + hs) - fn(spot=s - hs)) / (2 * hs), rel=1e-6)
    assert d["vega"] == pytest.approx((fn(vol=v + h) - fn(vol=v - h)) / (2 * h), rel=1e-6)


def test_parity_digital_and_iv():
    s, k, t, r, v, q = 100.0, 105.0, 1.0, 0.05, 0.2, 0.01
    call = vanilla(s, k, t, r, v, q)["price"]
    put = vanilla(s, k, t, r, v, q, "put")["price"]
    assert call - put == pytest.approx(s * np.exp(-q * t) - k * np.exp(-r * t))
    e = 0.001
    spread = (vanilla(s, k - e, t, r, v, q)["price"] - vanilla(s, k + e, t, r, v, q)["price"]) / (
        2 * e
    )
    assert digital(s, k, t, r, v, q)["price"] == pytest.approx(spread, abs=1e-9)
    for vol in [0.03, 0.2, 0.8, 2.0]:
        price = vanilla(s, k, t, r, vol, q)["price"]
        iv = implied_vol(price, s, k, t, r, q)
        assert vanilla(s, k, t, r, iv, q)["price"] == pytest.approx(price, abs=1e-8)
    with pytest.raises(ValueError):
        implied_vol(200, s, k, t, r, q)


@pytest.mark.parametrize("is_digital", [False, True])
def test_monte_carlo(is_digital):
    p, se = monte_carlo(
        100, 100, 1, 0.05, 0.2, 0.01, paths=100000, seed=42, digital_payoff=is_digital
    )
    exact = (digital if is_digital else vanilla)(100, 100, 1, 0.05, 0.2, 0.01)["price"]
    assert abs(p - exact) < 3 * se


def test_grid():
    grid = sensitivity(config()["options"])
    assert grid.loc[0.0, 0.0] == pytest.approx(0.0)
    assert grid.shape == (9, 5)
