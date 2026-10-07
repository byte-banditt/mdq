"""Black-Scholes and cash digitals; Greeks use unit vol/rate and annual theta."""

import numpy as np
import pandas as pd
from scipy.special import ndtr

from .data import ROOT

SQRT2PI = np.sqrt(2 * np.pi)


def _inputs(s, k, t, r, vol, q, kind):
    if kind not in {"call", "put"}:
        raise ValueError("kind must be call or put")
    s, k, t, r, vol, q = np.broadcast_arrays(
        *[np.asarray(x, dtype=float) for x in (s, k, t, r, vol, q)]
    )
    if (
        not all(np.isfinite(x).all() for x in (s, k, t, r, vol, q))
        or (s <= 0).any()
        or (k <= 0).any()
        or (t <= 0).any()
        or (vol <= 0).any()
    ):
        raise ValueError("Positive finite spot, strike, expiry and volatility required")
    d1 = (np.log(s / k) + (r - q + 0.5 * vol**2) * t) / (vol * np.sqrt(t))
    d2 = d1 - vol * np.sqrt(t)
    return s, k, t, r, vol, q, d1, d2, 1 if kind == "call" else -1


def vanilla(s, k, t, r, vol, q=0.0, kind="call"):
    s, k, t, r, vol, q, d1, d2, z = _inputs(s, k, t, r, vol, q, kind)
    ds = np.exp(-q * t)
    dk = np.exp(-r * t)
    pdf = np.exp(-0.5 * d1**2) / SQRT2PI
    return dict(
        price=z * (s * ds * ndtr(z * d1) - k * dk * ndtr(z * d2)),
        delta=z * ds * ndtr(z * d1),
        gamma=ds * pdf / (s * vol * np.sqrt(t)),
        vega=s * ds * pdf * np.sqrt(t),
        theta=-s * ds * pdf * vol / (2 * np.sqrt(t))
        + z * q * s * ds * ndtr(z * d1)
        - z * r * k * dk * ndtr(z * d2),
        rho=z * k * t * dk * ndtr(z * d2),
    )


def digital(s, k, t, r, vol, q=0.0, kind="call", cash=1.0):
    s, k, t, r, vol, q, d1, d2, z = _inputs(s, k, t, r, vol, q, kind)
    if cash < 0:
        raise ValueError("Cash payoff must be nonnegative")
    factor = cash * np.exp(-r * t)
    pdf = np.exp(-0.5 * d2**2) / SQRT2PI
    return dict(
        price=factor * ndtr(z * d2),
        delta=z * factor * pdf / (s * vol * np.sqrt(t)),
        vega=-z * factor * pdf * d1 / vol,
    )


def implied_vol(price, s, k, t, r, q=0.0, kind="call", tol=1e-10):
    z = 1 if kind == "call" else -1
    _inputs(s, k, t, r, 0.2, q, kind)
    lower = max(z * (s * np.exp(-q * t) - k * np.exp(-r * t)), 0.0)
    upper = s * np.exp(-q * t) if kind == "call" else k * np.exp(-r * t)
    if not lower < price < upper:
        raise ValueError("Price outside strict arbitrage bounds")
    lo = 1e-8
    hi = 1.0
    while vanilla(s, k, t, r, hi, q, kind)["price"] < price and hi < 128:
        hi *= 2
    if vanilla(s, k, t, r, hi, q, kind)["price"] < price:
        raise ValueError("Cannot bracket implied volatility")
    vol = min(0.2, hi)
    for _ in range(200):
        quote = vanilla(s, k, t, r, vol, q, kind)
        error = float(quote["price"] - price)
        if abs(error) < tol:
            return vol
        if error > 0:
            hi = vol
        else:
            lo = vol
        vega = float(quote["vega"])
        candidate = vol - error / vega if vega > 1e-12 else np.nan
        vol = candidate if lo < candidate < hi else (lo + hi) / 2
    raise ValueError("Implied volatility failed to converge")


def monte_carlo(s, k, t, r, vol, q=0.0, kind="call", paths=100000, seed=42, digital_payoff=False):
    _inputs(s, k, t, r, vol, q, kind)
    if paths < 2:
        raise ValueError("At least two paths required")
    terminal = s * np.exp(
        (r - q - 0.5 * vol**2) * t
        + vol * np.sqrt(t) * np.random.default_rng(seed).standard_normal(paths)
    )
    z = 1 if kind == "call" else -1
    payoff = (
        (z * (terminal - k) > 0).astype(float)
        if digital_payoff
        else np.maximum(z * (terminal - k), 0)
    )
    discounted = np.exp(-r * t) * payoff
    return float(discounted.mean()), float(discounted.std(ddof=1) / np.sqrt(paths))


def sensitivity(inputs):
    s, k, t, r, v, q = (inputs[x] for x in ("spot", "strike", "expiry", "rate", "vol", "q"))

    def value(spot, vol):
        return float(
            vanilla(spot, k, t, r, vol, q)["price"] - digital(spot, k, t, r, vol, q)["price"]
        )

    base = value(s, v)
    grid = pd.DataFrame(
        index=np.linspace(-0.1, 0.1, 9), columns=np.linspace(-0.05, 0.05, 5), dtype=float
    )
    for shock in grid.index:
        for dv in grid.columns:
            grid.loc[shock, dv] = value(s * (1 + shock), v + dv) - base
    grid.index.name = "spot_shock"
    grid.columns.name = "vol_change"
    return grid


def artifacts(cfg):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    p = cfg["options"]
    s, k, t, r, v, q = (p[x] for x in ("spot", "strike", "expiry", "rate", "vol", "q"))
    spot = np.linspace(0.7 * s, 1.3 * s, 301)
    times = np.linspace(0.001, 2, 301)
    for label, x, quotes, fields in [
        ("vanilla_spot", spot, vanilla(spot, k, t, r, v, q), ["delta", "gamma"]),
        ("vanilla_expiry", times, vanilla(s, k, times, r, v, q), ["delta", "gamma", "theta"]),
    ]:
        fig, axes = plt.subplots(len(fields), 1, figsize=(7, 3 * len(fields)))
        for ax, field in zip(np.atleast_1d(axes), fields):
            ax.plot(x, quotes[field])
            ax.set_ylabel(field)
            ax.grid(alpha=0.2)
        axes[-1].set_xlabel("Spot" if label.endswith("spot") else "Years to expiry")
        fig.tight_layout()
        fig.savefig(ROOT / "reports" / f"{label}.png")
        plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4))
    for time in [1.0, 0.1, 0.01, 0.001]:
        ax.plot(spot, digital(spot, k, time, r, v, q)["delta"], label=f"T={time:g}")
    ax.set(xlabel="Spot", ylabel="Digital delta")
    ax.legend()
    fig.tight_layout()
    fig.savefig(ROOT / "reports" / "digital_delta.png")
    plt.close(fig)
    grid = sensitivity(p)
    with pd.ExcelWriter(ROOT / "reports" / "sensitivity_grid.xlsx", engine="openpyxl") as writer:
        grid.to_excel(writer, sheet_name="Long call short digital")
    grid.to_csv(ROOT / "reports" / "sensitivity_grid.csv")
    return grid
