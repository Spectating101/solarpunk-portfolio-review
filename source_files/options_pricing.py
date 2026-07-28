"""
options_pricing.py
==================
Energy-Backed Derivative Pricing Framework
SolarPunk Research | Christopher Ongko | Yuan Ze University 2025

PURPOSE:
    Implements the physics-based pricing framework for energy-backed
    derivatives. Solves the cold-start problem by calibrating volatility
    from NASA POWER irradiance data rather than market-implied vol.

WHAT THIS IS:
    Pricing machinery for an energy monetary standard instrument.
    The derivative is the operational form of the energy standard.

WHAT THIS IS NOT:
    - A Bitcoin price prediction tool
    - A CEIR analysis script (see 01_foundation/ceir_analysis.py)
    - A live trading system

USAGE:
    python options_pricing.py
    # Outputs results to thesis_package/empirical_results/

THEORETICAL BASIS:
    - GBM justified at T <= 0.25 years (see RESEARCH_DESIGN.md §2.2)
    - Volatility from irradiance, not electricity price (cold-start solution)
    - Collar net credit is structural for ±10% strikes in a lognormal model;
      credit magnitude grows with sigma
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

SCRIPT_DIR = Path(__file__).resolve().parent
RESULTS_DIR = SCRIPT_DIR / "empirical_results"


# ─────────────────────────────────────────────────────────────────────────────
# PARAMETERS
# ─────────────────────────────────────────────────────────────────────────────

LOCATIONS = {
    "Taiwan": {
        "S0": 0.0525,   # LCOE $/kWh — Bureau of Energy Taiwan
        "sigma": 1.89,  # annualised irradiance vol — NASA POWER 2019-2024
        "r": 0.025,     # Taiwan 1yr government bond
        "lat": 23.5, "lon": 120.9
    },
    "Saudi Arabia": {
        "S0": 0.055, "sigma": 1.72, "r": 0.025,
        "lat": 24.7, "lon": 46.7
    },
    "Arizona, USA": {
        "S0": 0.058, "sigma": 1.65, "r": 0.045,
        "lat": 33.4, "lon": -112.1
    },
    "Brazil": {
        "S0": 0.095, "sigma": 1.98, "r": 0.135,
        "lat": -23.5, "lon": -46.6
    },
    "Germany": {
        "S0": 0.025, "sigma": 0.45, "r": 0.035,
        "lat": 48.1, "lon": 11.6
    }
}

T = 0.25          # Quarterly maturity (years)
N_BINOMIAL = 400  # Steps — convergence verified (see Table 3.2)
N_MC = 20000      # Monte Carlo paths — Taiwan base-case divergence is 2.08%

# Collar strikes
PUT_STRIKE_PCT  = 0.90   # 10% OTM put  (floor)
CALL_STRIKE_PCT = 1.10   # 10% OTM call (cap)

# Margin parameters (thesis §4.4)
Z_99 = 2.33         # 99th percentile
MARGIN_MULT = 1.50  # 1.5× VaR99%
MAINT_THRESH = 1.20 # 120% of max loss triggers liquidation

# Oracle error for hedge effectiveness (estimated current quality)
ORACLE_ERROR_PCT = 0.06  # 6% of spot price


# ─────────────────────────────────────────────────────────────────────────────
# CORE PRICING FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def bs_call(S, K, r, sigma, T):
    """
    Black-Scholes European call price.

    Parameters
    ----------
    S     : float — current spot price ($/kWh)
    K     : float — strike price ($/kWh)
    r     : float — risk-free rate (annualised)
    sigma : float — annualised volatility (irradiance-calibrated)
    T     : float — time to maturity (years)

    Returns
    -------
    float — call option price ($/kWh)
    """
    if sigma <= 0 or T <= 0:
        return max(S - K, 0)
    d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)
    return S*norm.cdf(d1) - K*np.exp(-r*T)*norm.cdf(d2)


def bs_put(S, K, r, sigma, T):
    """
    Black-Scholes European put price via put-call parity.
    Put-call parity: C - P = S - K*exp(-rT)
    """
    return bs_call(S, K, r, sigma, T) - S + K*np.exp(-r*T)


def binomial_call(S, K, r, sigma, T, N=N_BINOMIAL):
    """
    Binomial tree European call price (Cox-Ross-Rubinstein).
    Primary pricing method — validated against Black-Scholes.

    Convergence verified at N=400: price stabilises at $0.01917/kWh.
    See Table 3.2 for full convergence path.
    """
    dt = T / N
    u  = np.exp(sigma * np.sqrt(dt))
    d  = 1 / u
    p  = (np.exp(r * dt) - d) / (u - d)

    # Terminal stock prices
    j = np.arange(N+1)
    ST = S * u**j * d**(N-j)

    # Terminal payoffs
    V = np.maximum(ST - K, 0)

    # Backward induction
    discount = np.exp(-r * dt)
    for i in range(N):
        V = discount * (p * V[1:] + (1-p) * V[:-1])

    return V[0]


def monte_carlo_call(S, K, r, sigma, T, paths=N_MC, seed=42):
    """
    Monte Carlo European call price.
    Used for cross-method validation against binomial tree.
    Taiwan base-case divergence is 2.08% at 20,000 paths.
    """
    np.random.seed(seed)
    Z  = np.random.standard_normal(paths)
    ST = S * np.exp((r - 0.5*sigma**2)*T + sigma*np.sqrt(T)*Z)
    payoffs = np.maximum(ST - K, 0)
    price = np.exp(-r*T) * np.mean(payoffs)
    se    = np.exp(-r*T) * np.std(payoffs) / np.sqrt(paths)
    ci_lo = price - 1.96*se
    ci_hi = price + 1.96*se
    return price, se, ci_lo, ci_hi


def compute_greeks(S, K, r, sigma, T, dS=0.001, dsigma=0.01, dT=1/365):
    """
    Five Greeks via central-difference finite differences.

    Returns dict with: delta, gamma, vega, theta, rho
    """
    base = bs_call(S, K, r, sigma, T)
    return {
        "delta": (bs_call(S+dS, K, r, sigma, T) -
                  bs_call(S-dS, K, r, sigma, T)) / (2*dS),
        "gamma": (bs_call(S+dS, K, r, sigma, T) -
                  2*base +
                  bs_call(S-dS, K, r, sigma, T)) / dS**2,
        "vega":  (bs_call(S, K, r, sigma+dsigma, T) -
                  bs_call(S, K, r, sigma-dsigma, T)) / (2*dsigma),
        "theta": (bs_call(S, K, r, sigma, T+dT) -
                  bs_call(S, K, r, sigma, T-dT)) / (2*dT) * -1,
        "rho":   (bs_call(S, K, r+0.01, sigma, T) -
                  bs_call(S, K, r-0.01, sigma, T)) / 0.02
    }


# ─────────────────────────────────────────────────────────────────────────────
# MARGIN AND RISK FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def initial_margin(S, sigma, T, z=Z_99, mult=MARGIN_MULT):
    """
    VaR-based initial margin (thesis §4.4, Equation 4).

    Initial_Margin = mult × VaR_{99%}
    VaR_{99%} = S × [exp(z × σ × √T) - 1]

    Parameters
    ----------
    S     : spot price ($/kWh)
    sigma : annualised volatility
    T     : maturity (years)
    z     : z-score for confidence level (2.33 for 99%)
    mult  : multiplier above VaR (1.5 = buffer to ~99.9%)
    """
    var99 = S * (np.exp(z * sigma * np.sqrt(T)) - 1)
    return mult * var99


def hedge_effectiveness(sigma, oracle_error_pct, S, T):
    """
    Variance reduction from minimum variance hedge framework (Hull 2018).

    VR = σ_X² / (σ_X² + σ_ε²)

    Where:
    σ_X = payoff standard deviation = σ × S × √T
    σ_ε = oracle noise = oracle_error_pct × S

    Higher σ → higher VR → instrument more robust to oracle error.
    A fixed 6% error can produce ~99% VR at σ = 189%, but that single-point
    figure is only illustrative. The thesis should lead with oracle tolerance
    thresholds, not this fixed-error example.
    """
    sigma_X = sigma * S * np.sqrt(T)
    sigma_eps = oracle_error_pct * S
    return sigma_X**2 / (sigma_X**2 + sigma_eps**2)


# ─────────────────────────────────────────────────────────────────────────────
# COLLAR STRUCTURE
# ─────────────────────────────────────────────────────────────────────────────

def zero_premium_collar(S, r, sigma, T,
                        put_pct=PUT_STRIKE_PCT,
                        call_pct=CALL_STRIKE_PCT):
    """
    Zero-premium collar: buy OTM put + sell OTM call.

    Net cost = put_premium - call_premium
    When net_cost <= 0: producer receives net credit (zero upfront cost)
    With ±10% symmetric strikes in a lognormal model, this is structural:
    the sold call is closer to ATM in log-space and therefore always more
    expensive than the bought put. Sigma changes credit magnitude, not sign.

    Returns
    -------
    dict with put_K, call_K, put_px, call_px, net_cost, zero_premium
    """
    put_K  = S * put_pct    # floor strike
    call_K = S * call_pct   # cap strike

    put_px  = bs_put(S, put_K, r, sigma, T)
    call_px = bs_call(S, call_K, r, sigma, T)
    net     = put_px - call_px

    return {
        "put_strike":   put_K,
        "call_strike":  call_K,
        "put_premium":  put_px,
        "call_premium": call_px,
        "net_cost":     net,
        "zero_premium": net <= 0
    }


# ─────────────────────────────────────────────────────────────────────────────
# CROSS-LOCATION VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

def run_cross_location():
    """
    Validates pricing framework across five global solar markets.
    Demonstrates methodology is not calibrated only to Taiwan.

    Returns DataFrame with pricing results for all locations.
    """
    results = []

    for loc, params in LOCATIONS.items():
        S     = params["S0"]
        sigma = params["sigma"]
        r     = params["r"]
        K     = S  # ATM

        binomial = binomial_call(S, K, r, sigma, T)
        mc_price, mc_se, mc_lo, mc_hi = monte_carlo_call(S, K, r, sigma, T)
        put_price = bs_put(S, K, r, sigma, T)
        collar = zero_premium_collar(S, r, sigma, T)
        margin = initial_margin(S, sigma, T)
        hedge_eff = hedge_effectiveness(sigma, ORACLE_ERROR_PCT, S, T)

        pct_diff = abs(mc_price - binomial) / binomial * 100

        results.append({
            "Location":          loc,
            "S0 ($/kWh)":        S,
            "σ (%)":             f"{sigma:.0%}",
            "Call (Binomial)":   binomial,
            "Call (MC)":         mc_price,
            "Put (ATM)":         put_price,
            "% Diff (B vs MC)":  pct_diff,
            "Collar Net Cost":   collar["net_cost"],
            "Zero-Premium":      collar["zero_premium"],
            "Initial Margin":    margin,
            "Hedge Eff (6% err)":hedge_eff
        })

    return pd.DataFrame(results)


# ─────────────────────────────────────────────────────────────────────────────
# CONVERGENCE VALIDATION (Table 3.2)
# ─────────────────────────────────────────────────────────────────────────────

def convergence_table(S=0.0525, K=0.0525, r=0.025, sigma=1.89, T=0.25):
    """
    Reproduces Table 3.2: Binomial Tree Convergence.
    Shows price stabilises at N=400 steps.
    """
    steps = [50, 100, 200, 400, 800, 1200]
    prices = [binomial_call(S, K, r, sigma, T, N=n) for n in steps]
    pct_changes = [None] + [
        (prices[i] - prices[i-1]) / prices[i-1] * 100
        for i in range(1, len(prices))
    ]
    return pd.DataFrame({
        "Steps (N)":           steps,
        "Option Price ($/kWh)": [f"{p:.5f}" for p in prices],
        "Change from Previous": [f"+{c:.3f}%" if c else "—"
                                 for c in pct_changes]
    })


# ─────────────────────────────────────────────────────────────────────────────
# MAIN EXECUTION
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 65)
    print("ENERGY-BACKED DERIVATIVE PRICING FRAMEWORK")
    print("Physics-based volatility | Cold-start solution")
    print("=" * 65)

    # ── Taiwan Base Case ──────────────────────────────────────────
    p = LOCATIONS["Taiwan"]
    S0, sigma, r = p["S0"], p["sigma"], p["r"]
    K = S0

    print(f"\n── Taiwan Base Case ──────────────────────────────")
    print(f"  S₀ = ${S0}/kWh  |  σ = {sigma:.0%}  |  r = {r:.1%}  |  T = {T} yr")

    call_b  = binomial_call(S0, K, r, sigma, T)
    mc, se, lo, hi = monte_carlo_call(S0, K, r, sigma, T)
    put_b   = bs_put(S0, K, r, sigma, T)
    collar  = zero_premium_collar(S0, r, sigma, T)
    margin  = initial_margin(S0, sigma, T)
    greeks  = compute_greeks(S0, K, r, sigma, T)
    he      = hedge_effectiveness(sigma, ORACLE_ERROR_PCT, S0, T)
    diff_pct = abs(mc - call_b) / call_b * 100

    print(f"\n  Pricing:")
    print(f"    ATM Call (binomial):  ${call_b:.5f}/kWh")
    print(f"    ATM Call (MC):        ${mc:.5f}/kWh  95%CI[${lo:.5f}, ${hi:.5f}]")
    print(f"    ATM Put:              ${put_b:.5f}/kWh")
    print(f"    B vs MC divergence:   {diff_pct:.2f}%")
    print(f"\n  Collar (0.9K put + 1.1K call):")
    print(f"    Net cost to producer: ${collar['net_cost']:.5f}/kWh")
    print(f"    Zero-premium:         {'✓ Yes' if collar['zero_premium'] else '✗ No'}")
    print(f"\n  Risk:")
    print(f"    Initial margin (1.5×VaR₉₉%): ${margin:.4f}/kWh")
    print(f"    Illustrative hedge effectiveness (6% err):  {he:.1%}")
    print(f"\n  Greeks:")
    for g, v in greeks.items():
        print(f"    {g.capitalize():8s}: {v:.4f}")

    # ── Convergence Table ─────────────────────────────────────────
    print(f"\n── Binomial Convergence (Table 3.2) ──────────────")
    conv = convergence_table()
    print(conv.to_string(index=False))

    # ── Cross-Location Validation ─────────────────────────────────
    print(f"\n── Cross-Location Validation ──────────────────────")
    xl = run_cross_location()
    display_cols = ["Location", "σ (%)", "Call (Binomial)",
                    "Put (ATM)", "Collar Net Cost", "Zero-Premium"]
    print(xl[display_cols].to_string(index=False))

    print(
        f"\n  Net-credit collar observed: {xl['Zero-Premium'].sum()}/{len(xl)} locations "
        f"(structural for this strike pair, not a sigma-threshold result)"
    )

    # ── Save ──────────────────────────────────────────────────────
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    xl.to_csv(RESULTS_DIR / "cross_location_pricing.csv", index=False)

    steps = [50, 100, 200, 400, 800, 1200]
    conv_numeric = pd.DataFrame(
        {
            "steps": steps,
            "binomial_price": [
                binomial_call(S0, K, r, sigma, T, N=n) for n in steps
            ],
        }
    )
    conv_numeric.to_csv(RESULTS_DIR / "binomial_convergence.csv", index=False)
    conv.to_csv(RESULTS_DIR / "binomial_convergence_table.csv", index=False)

    summary_rows = []
    for loc, params in LOCATIONS.items():
        S, sigma, r = params["S0"], params["sigma"], params["r"]
        K = S
        b = binomial_call(S, K, r, sigma, T)
        mc_p, _, _, _ = monte_carlo_call(S, K, r, sigma, T)
        summary_rows.append(
            {
                "Location": loc,
                "S0": S,
                "sigma": sigma,
                "Binomial": b,
                "MonteCarlo": mc_p,
                "%Diff": (mc_p - b) / b * 100 if b else 0.0,
            }
        )
    pd.DataFrame(summary_rows).to_csv(
        RESULTS_DIR / "pricing_convergence_summary.csv", index=False
    )

    stress_rows = []
    for s0 in (0.042, 0.0525, 0.063):
        for sigma in (1.42, 1.89, 2.36):
            var99 = s0 * (np.exp(Z_99 * sigma * np.sqrt(T)) - 1)
            stress_rows.append(
                {
                    "S0": s0,
                    "sigma": sigma,
                    "VaR99_spot": var99,
                    "Initial_margin_1.5x": initial_margin(s0, sigma, T),
                }
            )
    pd.DataFrame(stress_rows).to_csv(
        RESULTS_DIR / "margin_stress_table.csv", index=False
    )

    print(f"\nResults saved to {RESULTS_DIR}")
    print("=" * 65)
