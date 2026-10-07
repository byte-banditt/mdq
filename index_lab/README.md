# Index Lab

Educational Python tools built on the existing mdq SQLite pipeline. Run from this directory with `python run_all.py`; run tests from repository root with `pytest`. No new downloads or invented equity observations. Configuration is JSON syntax in `config.yaml` (JSON is valid YAML); loading uses the standard library so no extra parser is required.

## Data and index decisions

See `docs/data_inventory.md` for actual schema, counts and dates printed by the rebuild. The DB has 21 stocks, not the full Nifty 50, plus `^NSEI`. No verified current constituents file was supplied. This run is a **20-stock sample demonstration**, not a full Nifty 50 strategy backtest. `data/nifty50_constituents.csv` records this status explicitly. TMPV is excluded by config because adjusted prices still have unexplained returns beyond 20%. The five missing benchmark bars prevent an uninterrupted Nifty 50 comparison. Benchmark is the monthly rebalanced equal-weight configured sample, gross and without costs; never label its results as Nifty 50. Supplying verified membership and sufficient prices is required for the requested full-universe version.

`adj_close` differs from close, but no corporate-actions table or adjustment provenance exists. Split/bonus/dividend adjustment completeness is **unverified**. Overnight adjusted returns beyond +/-20% are flagged and block constituent calculations. Holiday inference cannot distinguish genuine exchange holidays from whole-market provider outages; missing weekdays are review warnings, never invented sessions. Full history is required for every configured name; missing observations block, with no forward fill.

Momentum uses closes at or before calendar dates twelve months and one month before the decision date. Volatility uses 60 simple daily returns, sample standard deviation, annualized with 252 sessions. Stable sorting breaks equal scores by symbol. Both strategies start after the twelve-month warmup so comparisons share dates. Base level 1000 is published on the initial decision day, positions start next session. A truncated final month has no next-session rebalance. BaseIndex defines selection, equal weighting and rebalance; MomentumIndex and LowVolIndex specialize selection. This is the index code standardization step.

Stored weights are beginning-of-day weights. Post-return weights drift in proportion to each holding's gross return. Monthly targets execute after the decision close, before the following session return. Turnover is absolute purchases plus absolute sales; initial investment has turnover 1, a complete rotation 2. Cost is turnover times per-side bps; it reduces capital before the session return, so net return is `(1-cost)*(1+gross_return)-1`. Gross and net use the same holdings. Cost has no stock contribution and is accounted for separately. The modification demonstration independently rebuilds each index at 25 bps, 15 names and a reduced universe; no parameters are chosen from the results.

## Backtest and model limitations

- Survivorship bias: universe = current Nifty 50 constituents, so backtest is flattered.
- Flat bps cost only; no market impact, no taxes.
- Index parameters (10 names, 12-1, 60-day, 10 bps) were fixed before looking at results and are not tuned.
- Report exact date range and number of rebalances.
- Rates and structured-product models are textbook Black-76 / GBM Monte Carlo with illustrative inputs, not production models; no calibration to market data unless data is actually supplied.
- Sector map and betas are static/historical.

The first wording describes the target design. This supplied-data demonstration uses an unverified fixed stock sample instead; it also has selection and survivorship bias. Never claim a current full Nifty 50 universe for this run.

## Monitor, attribution and stress

mdq's six checks run on source rows without changing the DB. Added overnight-jump and calendar checks, required held-price checks, weight sums, trailing return outliers and rebalance limits produce an exception log. The sigma estimate uses only the previous 60 returns; holidays are potential gaps requiring review. Rebalance proposals show pre-trade closing drifted weights, targets, trades and cost estimates, without human approval. Debug with `python scripts/explain_day.py --index MOM10 --date YYYY-MM-DD` after rebuilding.

Sector map is a project-authored static business grouping, not official NSE or GICS data. Source label is recorded in every row. Monthly benchmark targets equal weights at the first session of each month and then drifts. Brinson uses first-session weights and each stock's compounded return over that month. Empty portfolio sectors use benchmark sector returns so selection and interaction cancel there. Allocation + selection + interaction reconcile to **gross** active return monthly. Net active return includes a separately reported cost effect. Arithmetic sums across months do not equal compounded active return; the compounding residual is reported explicitly. Full-period stock contributions multiply each daily contribution by prior gross wealth, reconciling to gross cumulative return.

Historical replay uses latest closing holdings and frozen stock units over the three worst non-overlapping 20-session proxy windows when 2020 is unavailable. This describes current exposure replay, not historical strategy returns or predictive risk. Drawdown includes initial wealth. Market shocks multiply estimated stock betas by shocks; sector scenarios directly shock selected sector returns. Betas use sample return covariance divided by benchmark variance over the full backtest, and are historical estimates. Composition uses latest closing drifted weights, top-three concentration and sum of squared weights (HHI).

## Equity options

European Black-Scholes assumes constant volatility, continuous dividend yield and continuously compounded rate. Positive spot, strike, maturity and volatility are required; expiry payoff is handled in payoff diagrams separately. Vega is price change per 1.0 volatility change (divide by 100 for one vol point); rho per 1.0 rate change; theta is annual calendar-time decay. Cash digital pays one currency unit. Analytic derivatives are tested against central differences, put-call parity and the tight strike call-spread limit. Seeded terminal GBM Monte Carlo uses 100,000 paths with sample standard error. Implied volatility maintains an arbitrage-valid bracket, uses Newton when inside it and otherwise bisects. Scenario grid is long one European call minus one unit-cash digital, and reports currency P&L for spot and absolute volatility changes, not historical option quotes.

## Rates and exotics

`data/rates_inputs.csv` contains explicitly illustrative continuously compounded zero rates. Discount factors are exp(-zero_rate * tenor), interpolated linearly in their logarithms with DF(0)=1; no extrapolation or par-rate bootstrapping is used. Times are ACT/365 year fractions supplied as numbers; payments are semiannual with a possible final stub. No business-day adjustments, multi-curve basis, collateral or day-count subtleties. Payer fixed swap PV equals discounted float minus fixed leg; the forward floating leg is DF(start)-DF(end). DV01 is the central PV change for a parallel +1bp zero-rate shift, with its sign retained.

Black-76 assumes positive lognormal forwards and constant illustrative volatility. Caplets fix at period starts and pay at ends; the initial fixing at time zero is deterministic intrinsic value. Caps/floors sum caplets/floorlets. Swaptions use forward par swap rate and today's discounted annuity. Parity residuals are computed, not filled with literal zeros. Rate cash digital uses the same normal-CDF formula as equity digital under the forward measure, discounted to payment. Margrabe prices zero-strike exchange; nonzero-strike spread options use correlated two-asset terminal GBM Monte Carlo. Equity range accrual pays a maturity-discounted annual coupon times term times fraction of 252 observation days within the range. Its analytic strip adjusts each equity digital's observation-date discount to maturity discount; the MC correlation across observation days affects standard error, not expected coupon.

`--fast` skips heavy spread/range-accrual and structured MC. It still rebuilds indices, oversight, attribution and analytic plots/products; omitted MC outputs must never be claimed as newly computed.

## Structured products

Autocallable is an illustrative unit-notional note on GBM with constant volatility and fixed initial reference. Daily simulation monitors knock-in, including initial spot; pre-maturity quarterly observations test autocall at or above the reference barrier. First call redeems principal plus simple annual coupon accrued to that observation, discounted from its payment date. If not called, maturity pays principal plus accrued coupon; a prior knock-in and terminal spot below reference reduce principal to terminal/reference. Coupon is unconditional in this educational contract. Loss probability refers to principal loss, excluding coupon. Issuer credit, funding, dividends changing over time and market calibration are absent. Knock-in is discretely monitored, not continuously monitored. Observation dates are rounded to the daily grid; current quarter-year dates land exactly on it. Common random numbers reuse identical normal shocks for spot/volatility bumps; reference remains fixed. Delta is per unit currency spot and vega per unit vol, both for unit notional. Prices and standard errors use configured paths; delta plots use 10,000 shared paths and still have sampling noise. A real positive-time price may be smooth despite discontinuous payoff barriers; plots show sensitivity, not proof of mathematical price discontinuity.

The vol smile is an explicitly illustrative function of strike, not observed market data or a calibrated arbitrage-free surface. Digital under skew is computed as the strike derivative of smile call prices, including smile slope; put spreads price each strike with its own vol. The autocallable payoff chart shows conditional maturity slices because terminal spot alone cannot determine a path-dependent payoff. Primer is headings only, deliberately left for the author.

## Reports and reproducibility

`python run_all.py` prints source inventory and rebuilds CSV, numeric XLSX, PNG, PPTX and generated documents. `python run_all.py --fast` skips heavy MC products. `python -m indexkit.reporting --period monthly --asof 2026-09-30 --fast` rebuilds standard reports from all history up to that supplied date, including methodology warmup; nontrading as-of dates use the last observed session. Dates beyond supplied data are rejected. Run from `index_lab/`, with the root mdq package installed (`pip install -e ..`) or use `PYTHONPATH=../src`. All figures use a noninteractive matplotlib backend. Output dates and rebalance counts come from calculated results in Summary and run_manifest.json.

CAGR uses actual elapsed calendar days / 365.25. Volatility is sample daily simple-return standard deviation times sqrt(252). Sharpe uses daily geometric equivalent of configured annual risk-free rate (default 5%), mean daily excess return / sample standard deviation times sqrt(252). Tracking error and information ratio use synchronous daily active returns vs the sample proxy. Maximum drawdown includes initial base. Average turnover includes initial investment. Gross/net metrics are separate rows, with same holdings and different modeled capital costs. These conventions differ from cash flow returns or production total-return vendor benchmarks. Excel cells store numbers, dates and formats; percentages are not text. Four-slide factsheet and commentary state sample limitations.

Methodology and change note documents are educational drafts. Launch form approvals remain blank. The flow primer is a manual-writing template; generated commentary is not a completed original article. No live-index operation is claimed.

Maturity redemption is not counted as an early call. Probability CSV gives both first-call and cumulative early-call probabilities. Config controls curve path, payment schedule, spread inputs, accrual range, skew slope, simulation steps, plot paths and Greek bumps. Source DB stays at its existing mdq path instead of being copied. Static sample and sector CSVs are tracked; market-price DB is local and must be provided by mdq.

## Optional Java verification

Java implements European price/delta with dividend yield and a normal-CDF power series. `python java_bs/generate_reference.py` computes five fixed-input Python quotes; `javac java_bs/BlackScholes.java` then `java -cp java_bs BlackScholes java_bs/python_reference.csv` verifies prices within 1e-9 and deltas within 1e-11. pytest compiles in a temporary directory and runs this check when Java is available. R cross-checks are not implemented.

## Completion limits

Index, monitoring, attribution, stress, derivatives, reporting and optional Java cross-check tools are implemented. End-to-end rebuild and all pytest checks run locally. Four injected faults block calculation; monthly attribution, option Greeks/MC, rates parity and digital-strip checks pass. Full current Nifty 50 input is unavailable, so the requested full-universe and true-Nifty attribution remain unfulfilled. Models and reports use a disclosed sample proxy. Multi-asset and R are absent. The flow primer remains a template.

## Git contents

Source, tests, config, static educational CSVs, runbook and document templates are versioned. SQLite market data, report outputs, generated result documents, Java references/classes, caches and personal career notes are ignored. Run mdq ingestion to provision the local source DB before running `run_all.py` or the Index Lab integration tests. Generated reports stay under `reports/` and are recreated locally.
