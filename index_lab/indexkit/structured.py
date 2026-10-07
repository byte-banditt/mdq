"""Illustrative daily-monitored knock-in autocallable; fixed contractual reference."""

import numpy as np
import pandas as pd

from .data import ROOT
from .options import digital, vanilla


def factors(vol, r, q, observations, paths, seed, steps=252):
    observations = np.asarray(observations, dtype=float)
    if (
        paths < 2
        or steps < 1
        or vol < 0
        or len(observations) == 0
        or (observations <= 0).any()
        or (np.diff(observations) <= 0).any()
    ):
        raise ValueError("Invalid path parameters")
    term = observations[-1]
    dt = term / steps
    ticks = np.rint(observations / dt).astype(int)
    if (ticks < 1).any() or len(np.unique(ticks)) != len(ticks):
        raise ValueError("Observation dates collapse on simulation grid")
    state = np.ones(paths)
    minimum = state.copy()
    obs = []
    rng = np.random.default_rng(seed)
    for step in range(1, steps + 1):
        state *= np.exp(
            (r - q - 0.5 * vol**2) * dt + vol * np.sqrt(dt) * rng.standard_normal(paths)
        )
        minimum = np.minimum(minimum, state)
        if step in ticks:
            obs.append(state.copy())
    return np.asarray(obs), minimum, ticks * dt


def payoff(spot, reference, obs, minimum, times, r, coupon, autocall_barrier, knock_in):
    if min(spot, reference, autocall_barrier, knock_in) <= 0 or coupon < 0:
        raise ValueError("Invalid contract")
    paths = obs.shape[1]
    alive = np.ones(paths, dtype=bool)
    pv = np.zeros(paths)
    prob = []
    for i, time in enumerate(times):
        called = (
            alive & (spot * obs[i] >= reference * autocall_barrier)
            if i < len(times) - 1
            else np.zeros(paths, dtype=bool)
        )
        pv[called] = (1 + coupon * time) * np.exp(-r * time)
        prob.append(float(called.mean()))
        alive[called] = False
    terminal = spot * obs[-1]
    loss = alive & (spot * minimum <= reference * knock_in) & (terminal < reference)
    principal = np.where(loss, terminal / reference, 1.0)
    pv[alive] = (principal[alive] + coupon * times[-1]) * np.exp(-r * times[-1])
    return dict(
        price=float(pv.mean()),
        se=float(pv.std(ddof=1) / np.sqrt(paths)),
        early_call_prob=prob,
        capital_loss_prob=float(loss.mean()),
    )


def autocallable(
    spot,
    reference,
    vol,
    r,
    q,
    observations,
    coupon=0.08,
    autocall_barrier=1.0,
    knock_in=0.6,
    paths=100000,
    seed=42,
    steps=252,
):
    obs, minimum, times = factors(vol, r, q, observations, paths, seed, steps)
    return payoff(spot, reference, obs, minimum, times, r, coupon, autocall_barrier, knock_in)


def greeks(inputs, paths=100000, seed=42):
    p = dict(inputs)
    reference = p.pop("spot")

    def quote(spot, vol):
        return autocallable(
            spot,
            reference,
            vol,
            p["rate"],
            p["q"],
            p["observations"],
            p["coupon"],
            p["autocall_barrier"],
            p["knock_in"],
            paths,
            seed,
            p.get("steps", 252),
        )["price"]

    hs = reference * p.get("spot_bump_ratio", 0.005)
    hv = p.get("vol_bump", 0.005)
    if p["vol"] <= hv:
        raise ValueError("Volatility bump requires positive lower volatility")
    return dict(
        delta=(quote(reference + hs, p["vol"]) - quote(reference - hs, p["vol"])) / (2 * hs),
        vega=(quote(reference, p["vol"] + hv) - quote(reference, p["vol"] - hv)) / (2 * hv),
    )


def skew_prices(inputs, settings=None):
    settings = settings or {"slope": 0.3, "min_vol": 0.05, "max_vol": 0.8}
    s = inputs["spot"]
    t = inputs["expiry"]
    r = inputs["rate"]
    q = inputs["q"]
    v = inputs["vol"]

    def skew(k):
        return np.clip(
            v + settings["slope"] * (1 - k / s), settings["min_vol"], settings["max_vol"]
        )

    rows = []
    for k in np.linspace(0.8 * s, 1.2 * s, 41):
        e = 0.001 * s
        flat = float(digital(s, k, t, r, v, q)["price"])
        # Strike derivative includes smile slope; not a constant-vol digital evaluation.
        smile = float(
            (
                vanilla(s, k - e, t, r, skew(k - e), q)["price"]
                - vanilla(s, k + e, t, r, skew(k + e), q)["price"]
            )
            / (2 * e)
        )
        low = k - 0.05 * s
        flat_spread = float(
            vanilla(s, k, t, r, v, q, "put")["price"] - vanilla(s, low, t, r, v, q, "put")["price"]
        )
        smile_spread = float(
            vanilla(s, k, t, r, skew(k), q, "put")["price"]
            - vanilla(s, low, t, r, skew(low), q, "put")["price"]
        )
        rows.append(
            dict(
                strike=k,
                illustrative_vol=skew(k),
                flat_digital=flat,
                skew_digital=smile,
                flat_put_spread=flat_spread,
                skew_put_spread=smile_spread,
            )
        )
    return pd.DataFrame(rows)


def artifacts(cfg, fast=False):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    p = cfg["structured"]
    s = p["spot"]
    table = skew_prices(cfg["options"], cfg["skew"])
    table.to_csv(ROOT / "reports/illustrative_skew.csv", index=False)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, field in zip(axes, ["digital", "put_spread"]):
        ax.plot(table.strike, table[f"flat_{field}"], label="Flat vol")
        ax.plot(table.strike, table[f"skew_{field}"], label="Illustrative skew")
        ax.set(xlabel="Strike", ylabel=field)
        ax.legend()
    fig.suptitle("Illustrative skew, not market data")
    fig.tight_layout()
    fig.savefig(ROOT / "reports/illustrative_skew.png")
    plt.close(fig)
    x = np.linspace(0.3 * s, 1.6 * s, 300)
    fig, axes = plt.subplots(2, 2, figsize=(10, 7))
    axes[0, 0].plot(x, np.maximum(x - s, 0))
    axes[0, 0].set_title("Call payoff (no premium)")
    axes[0, 1].plot(x, (x > s).astype(float))
    axes[0, 1].set_title("Unit cash digital")
    axes[1, 0].plot(x, np.maximum(s - x, 0) - np.maximum(0.9 * s - x, 0))
    axes[1, 0].set_title("Long put spread")
    axes[1, 1].plot(
        x,
        np.minimum(x / s, 1) + p["coupon"] * p["observations"][-1],
        label="No autocall; prior knock-in",
    )
    axes[1, 1].plot(
        x,
        np.full(len(x), 1 + p["coupon"] * p["observations"][-1]),
        label="No autocall; no knock-in",
    )
    axes[1, 1].set_title("Autocallable conditional maturity slices")
    axes[1, 1].legend(fontsize=7)
    for ax in axes.flat:
        ax.set_xlabel("Terminal spot")
        ax.set_ylabel("Payoff")
        ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(ROOT / "reports/payoffs.png")
    plt.close(fig)
    if fast:
        return None
    quote = autocallable(
        s,
        s,
        p["vol"],
        p["rate"],
        p["q"],
        p["observations"],
        p["coupon"],
        p["autocall_barrier"],
        p["knock_in"],
        cfg["mc_paths"],
        cfg["seed"],
        p["steps"],
    )
    g = greeks(p, cfg["mc_paths"], cfg["seed"])
    pd.DataFrame(
        [
            dict(
                price=quote["price"],
                se=quote["se"],
                capital_loss_prob=quote["capital_loss_prob"],
                **g,
            )
        ]
    ).to_csv(ROOT / "reports/autocallable.csv", index=False)
    pd.DataFrame(
        {
            "observation": p["observations"],
            "first_call_probability": quote["early_call_prob"],
            "cumulative_call_probability": np.cumsum(quote["early_call_prob"]),
        }
    ).to_csv(ROOT / "reports/autocall_probabilities.csv", index=False)
    obs, minimum, times = factors(
        p["vol"], p["rate"], p["q"], p["observations"], p["plot_paths"], cfg["seed"], p["steps"]
    )
    spots = np.linspace(0.5 * s, 1.2 * s, 51)
    bump = p["spot_bump_ratio"] * s

    def val(spot):
        return payoff(
            spot,
            s,
            obs,
            minimum,
            times,
            p["rate"],
            p["coupon"],
            p["autocall_barrier"],
            p["knock_in"],
        )["price"]

    deltas = np.array([(val(spot + bump) - val(spot - bump)) / (2 * bump) for spot in spots])
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(spots, deltas)
    ax.axvline(s * p["knock_in"], linestyle="--", label="Knock-in reference")
    ax.axvline(s * p["autocall_barrier"], linestyle=":", label="Autocall reference")
    ax.set(
        xlabel="Spot",
        ylabel="Delta per unit notional",
        title="MC delta; barrier sensitivity, sampling noise",
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(ROOT / "reports/autocall_delta.png")
    plt.close(fig)
    return quote
