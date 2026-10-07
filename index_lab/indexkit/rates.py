"""Textbook curve, Black-76 products and transparent GBM exotic checks."""

import numpy as np
import pandas as pd
from scipy.special import ndtr

from .data import ROOT
from .options import digital


class DiscountCurve:
    def __init__(self, tenors, zero_rates):
        self.tenors = np.asarray(tenors, dtype=float)
        self.zero_rates = np.asarray(zero_rates, dtype=float)
        if (
            self.tenors.ndim != 1
            or len(self.tenors) != len(self.zero_rates)
            or len(self.tenors) == 0
            or not np.isfinite(self.tenors).all()
            or not np.isfinite(self.zero_rates).all()
            or (self.tenors <= 0).any()
            or (np.diff(self.tenors) <= 0).any()
        ):
            raise ValueError("Sorted unique positive tenors and finite zero rates required")

    def df(self, t):
        t = np.asarray(t, dtype=float)
        if not np.isfinite(t).all() or (t < 0).any() or (t > self.tenors[-1]).any():
            raise ValueError("Curve request outside input horizon")
        return np.exp(np.interp(t, np.r_[0, self.tenors], np.r_[0, -self.tenors * self.zero_rates]))

    def forward(self, start, end):
        if end <= start:
            raise ValueError("Forward interval must be positive")
        return (self.df(start) / self.df(end) - 1) / (end - start)

    def bumped(self, bump):
        return DiscountCurve(self.tenors, self.zero_rates + bump)


def schedule(start, end, frequency=2):
    if frequency <= 0 or end <= start:
        raise ValueError("Invalid payment schedule")
    payments = np.arange(start + 1 / frequency, end + 1e-10, 1 / frequency)
    if len(payments) == 0 or payments[-1] < end - 1e-10:
        payments = np.r_[payments, end]
    return payments, np.diff(np.r_[start, payments])


def annuity(curve, start, end, frequency=2):
    payments, accrual = schedule(start, end, frequency)
    return float(np.sum(accrual * curve.df(payments)))


def par_swap_rate(curve, start, end, frequency=2):
    return float((curve.df(start) - curve.df(end)) / annuity(curve, start, end, frequency))


def swap(curve, fixed, start=0.0, end=5.0, notional=1.0, frequency=2):
    fixed_pv = notional * fixed * annuity(curve, start, end, frequency)
    float_pv = notional * (curve.df(start) - curve.df(end))
    return dict(
        price=float(float_pv - fixed_pv), fixed_pv=float(fixed_pv), float_pv=float(float_pv)
    )


def dv01(curve, fixed, start=0.0, end=5.0, notional=1.0, frequency=2):
    return (
        swap(curve.bumped(0.0001), fixed, start, end, notional, frequency)["price"]
        - swap(curve.bumped(-0.0001), fixed, start, end, notional, frequency)["price"]
    ) / 2


def black76(forward, strike, expiry, vol, discount=1.0, kind="call"):
    if kind not in {"call", "put"} or min(forward, strike, vol, discount) <= 0 or expiry < 0:
        raise ValueError(
            "Black-76 needs positive forward, strike, vol, discount and nonnegative expiry"
        )
    z = 1 if kind == "call" else -1
    if expiry == 0:
        return discount * max(z * (forward - strike), 0.0)
    d1 = (np.log(forward / strike) + 0.5 * vol**2 * expiry) / (vol * np.sqrt(expiry))
    d2 = d1 - vol * np.sqrt(expiry)
    return float(discount * z * (forward * ndtr(z * d1) - strike * ndtr(z * d2)))


def rate_digital(curve, forward, strike, expiry, payment, vol, kind="call", cash=1.0):
    if payment < expiry:
        raise ValueError("Digital payment before fixing")
    return float(
        curve.df(payment) * digital(forward, strike, expiry, 0.0, vol, 0.0, kind, cash)["price"]
    )


def caplet(curve, start, end, strike, vol, notional=1.0, kind="call"):
    return (
        notional
        * (end - start)
        * black76(float(curve.forward(start, end)), strike, start, vol, float(curve.df(end)), kind)
    )


def cap_floor(curve, strike, start=0.0, end=5.0, vol=0.2, notional=1.0, frequency=2, kind="call"):
    payments, _ = schedule(start, end, frequency)
    previous = np.r_[start, payments[:-1]]
    return float(
        sum(caplet(curve, s, e, strike, vol, notional, kind) for s, e in zip(previous, payments))
    )


def swaption(curve, strike, expiry=1.0, end=5.0, vol=0.2, notional=1.0, frequency=2, kind="payer"):
    if kind not in {"payer", "receiver"}:
        raise ValueError("Invalid swaption kind")
    return notional * black76(
        par_swap_rate(curve, expiry, end, frequency),
        strike,
        expiry,
        vol,
        annuity(curve, expiry, end, frequency),
        "call" if kind == "payer" else "put",
    )


def margrabe(s1, s2, t, v1, v2, rho, q1=0.0, q2=0.0):
    if min(s1, s2, t, v1, v2) <= 0 or not -1 <= rho <= 1:
        raise ValueError("Invalid spread inputs")
    vol = np.sqrt(max(v1 * v1 + v2 * v2 - 2 * rho * v1 * v2, 0))
    a = s1 * np.exp(-q1 * t)
    b = s2 * np.exp(-q2 * t)
    if vol == 0:
        return max(a - b, 0.0)
    d1 = (np.log(a / b) + 0.5 * vol**2 * t) / (vol * np.sqrt(t))
    d2 = d1 - vol * np.sqrt(t)
    return float(a * ndtr(d1) - b * ndtr(d2))


def spread_mc(s1, s2, k, t, r, v1, v2, rho, q1=0.0, q2=0.0, paths=100000, seed=42):
    margrabe(s1, s2, t, v1, v2, rho, q1, q2)
    if paths < 2:
        raise ValueError("At least two paths required")
    z = np.random.default_rng(seed).standard_normal((2, paths))
    z2 = rho * z[0] + np.sqrt(1 - rho**2) * z[1]
    a = s1 * np.exp((r - q1 - 0.5 * v1**2) * t + v1 * np.sqrt(t) * z[0])
    b = s2 * np.exp((r - q2 - 0.5 * v2**2) * t + v2 * np.sqrt(t) * z2)
    payoff = np.exp(-r * t) * np.maximum(a - b - k, 0.0)
    return float(payoff.mean()), float(payoff.std(ddof=1) / np.sqrt(paths))


def range_accrual(
    s,
    lower,
    upper,
    t,
    r,
    vol,
    q=0.0,
    coupon=0.05,
    notional=1.0,
    observations=252,
    paths=100000,
    seed=42,
):
    if not 0 < lower < upper or t <= 0 or observations < 1 or paths < 2:
        raise ValueError("Invalid range accrual inputs")
    dates = np.linspace(t / observations, t, observations)
    dt = t / observations
    state = np.full(paths, float(s))
    inside = np.zeros(paths)
    rng = np.random.default_rng(seed)
    for _ in dates:
        state *= np.exp(
            (r - q - 0.5 * vol**2) * dt + vol * np.sqrt(dt) * rng.standard_normal(paths)
        )
        inside += (state >= lower) & (state <= upper)
    payoff = notional * coupon * t * np.exp(-r * t) * inside / observations
    lower_price = digital(s, lower, dates, r, vol, q)["price"]
    upper_price = digital(s, upper, dates, r, vol, q)["price"]
    strip = float(
        notional * coupon * t * np.mean((lower_price - upper_price) * np.exp(-r * (t - dates)))
    )
    return dict(
        price=float(payoff.mean()),
        se=float(payoff.std(ddof=1) / np.sqrt(paths)),
        digital_strip=strip,
    )


def pricing_sheet(cfg, fast=False):
    inputs = pd.read_csv(ROOT / cfg["curve_inputs"])
    curve = DiscountCurve(inputs.tenor, inputs.zero_rate)
    settings = cfg["rates"]
    n = settings["notional"]
    v = settings["vol"]
    start = settings["start"]
    end = settings["end"]
    frequency = settings["frequency"]
    expiry = settings["swaption_expiry"]
    k = par_swap_rate(curve, start, end, frequency)
    cap = cap_floor(curve, k, start, end, v, n, frequency)
    floor = cap_floor(curve, k, start, end, v, n, frequency, "put")
    pv = swap(curve, k, start, end, n, frequency)["price"]
    payer = swaption(curve, k, expiry, end, v, n, frequency)
    receiver = swaption(curve, k, expiry, end, v, n, frequency, "receiver")
    fwd = swap(curve, k, expiry, end, n, frequency)["price"]
    common = dict(notional=n, strike=k, start=start, end=end, frequency=frequency, vol=v)
    rows = [
        dict(
            product="Swap (payer fixed)",
            **common,
            price=pv,
            DV01=dv01(curve, k, start, end, n, frequency),
            parity_residual=pv,
        ),
        dict(product="Cap", **common, price=cap, parity_residual=cap - floor - pv),
        dict(product="Floor", **common, price=floor, parity_residual=cap - floor - pv),
        dict(
            product="Payer swaption",
            **common,
            expiry=expiry,
            price=payer,
            parity_residual=payer - receiver - fwd,
        ),
        dict(
            product="Receiver swaption",
            **common,
            expiry=expiry,
            price=receiver,
            parity_residual=payer - receiver - fwd,
        ),
    ]
    from .options import digital as equity_digital
    from .options import vanilla

    p = cfg["options"]
    s, k, t, r, vol, q = (p[x] for x in ("spot", "strike", "expiry", "rate", "vol", "q"))
    for product, kind in [("European call", "call"), ("European put", "put")]:
        rows.append(
            dict(
                product=product,
                spot=s,
                strike=k,
                expiry=t,
                rate=r,
                vol=vol,
                q=q,
                **{a: float(b) for a, b in vanilla(s, k, t, r, vol, q, kind).items()},
            )
        )
    rows.append(
        dict(
            product="Equity cash digital",
            spot=s,
            strike=k,
            expiry=t,
            rate=r,
            vol=vol,
            q=q,
            **{a: float(b) for a, b in equity_digital(s, k, t, r, vol, q).items()},
        )
    )
    payment = expiry + 1 / frequency
    f = float(curve.forward(expiry, payment))
    dk = settings["digital_strike"]
    rows.append(
        dict(
            product="Rate cash digital",
            forward=f,
            strike=dk,
            expiry=expiry,
            payment=payment,
            vol=v,
            price=rate_digital(curve, f, dk, expiry, payment, v),
        )
    )
    sp = cfg["spread"]
    a, b, st, sr, v1, v2, rho, q1, q2 = (
        sp[x]
        for x in ("spot1", "spot2", "expiry", "rate", "vol1", "vol2", "correlation", "q1", "q2")
    )
    common = dict(
        spot=a, spot2=b, expiry=st, rate=sr, vol=v1, vol2=v2, correlation=rho, q1=q1, q2=q2
    )
    exact = margrabe(a, b, st, v1, v2, rho, q1, q2)
    rows.append(dict(product="Margrabe exchange", **common, strike=0.0, price=exact))
    if not fast:
        for strike in [0.0, sp["strike"]]:
            mc, se = spread_mc(
                a, b, strike, st, sr, v1, v2, rho, q1, q2, paths=cfg["mc_paths"], seed=cfg["seed"]
            )
            rows.append(
                dict(
                    product=f"Spread MC K={strike:g}",
                    **common,
                    strike=strike,
                    price=mc,
                    se=se,
                    parity_residual=mc - exact if strike == 0 else np.nan,
                )
            )
        settings = cfg["range_accrual"]
        lower = settings["lower_ratio"] * s
        upper = settings["upper_ratio"] * s
        accrual = range_accrual(
            s,
            lower,
            upper,
            t,
            r,
            vol,
            q,
            coupon=settings["coupon"],
            observations=settings["observations"],
            paths=cfg["mc_paths"],
            seed=cfg["seed"],
        )
        rows.append(
            dict(
                product="Equity range accrual",
                spot=s,
                lower=lower,
                upper=upper,
                expiry=t,
                rate=r,
                vol=vol,
                q=q,
                coupon=settings["coupon"],
                observations=settings["observations"],
                **accrual,
                parity_residual=accrual["price"] - accrual["digital_strip"],
            )
        )
    table = pd.DataFrame(rows)

    def checked(row):
        if pd.isna(row.get("parity_residual")):
            return None
        tolerance = 3 * row["se"] if pd.notna(row.get("se")) else 1e-8
        return bool(abs(row["parity_residual"]) <= tolerance)

    table["parity_pass"] = table.apply(checked, axis=1)
    table.to_csv(ROOT / "reports/derivatives_pricing_sheet.csv", index=False)
    with pd.ExcelWriter(
        ROOT / "reports/derivatives_pricing_sheet.xlsx", engine="openpyxl"
    ) as writer:
        table.to_excel(writer, index=False, sheet_name="Prices")
        inputs.to_excel(writer, index=False, sheet_name="Illustrative zero curve")
        from .reporting import format_workbook

        format_workbook(writer.book)
    return table
