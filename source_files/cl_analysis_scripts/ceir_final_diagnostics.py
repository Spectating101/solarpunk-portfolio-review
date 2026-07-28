#!/usr/bin/env python3
"""Final CEIR closure diagnostics — stationarity, non-overlapping returns, negative controls."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import mstats
from statsmodels.tsa.stattools import adfuller, coint

PKG = Path(__file__).resolve().parent
RESULTS = PKG / "empirical_results"
PANEL = RESULTS / "bitcoin_ceir_analysis_ready.csv"
COMPLETE = RESULTS / "bitcoin_ceir_complete.csv"
CHINA_BAN = pd.Timestamp("2021-06-20")
OUT_CSV = RESULTS / "ceir_final_negative_controls.csv"
OUT_MD = PKG / "CEIR_FINAL_DIAGNOSIS.md"


def adf_p(series: pd.Series) -> float:
    s = series.dropna().astype(float)
    if len(s) < 50:
        return float("nan")
    return float(adfuller(s, autolag="AIC")[1])


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    out = df.sort_values("Date").reset_index(drop=True).copy()
    if "in_analysis_period" in out.columns:
        out = out[out["in_analysis_period"] == 1].copy()
    out["ret_30d"] = out["Price"].astype(float).shift(-30) / out["Price"].astype(float) - 1
    # non-overlapping: keep every 30th observation after first valid
    out["ret_30d_nonoverlap"] = np.nan
    valid = out["ret_30d"].notna()
    idx = np.where(valid)[0]
    keep = idx[::30]
    out.loc[out.index[keep], "ret_30d_nonoverlap"] = out.loc[out.index[keep], "ret_30d"]
    # monthly last-day return to next month end approx: use period ends
    out["ym"] = out["Date"].dt.to_period("M")
    month_end = out.groupby("ym", as_index=False).tail(1).copy()
    month_end["ret_1m"] = month_end["Price"].astype(float).shift(-1) / month_end["Price"].astype(float) - 1
    out = out.merge(month_end[["ym", "ret_1m"]], on="ym", how="left")
    out.loc[out["Date"] != out.groupby("ym")["Date"].transform("max"), "ret_1m"] = np.nan

    daily_kwh = out["Energy_TWh_Annual"].astype(float) * 1e9 / 365.0
    # rebuild ratios on analysis window using complete cum through each date
    # For fair compare use panel Market_Cap with reconstructed denominators from complete
    out["log_ceir_w"] = mstats.winsorize(out["log_CEIR"].astype(float), limits=[0.01, 0.01])
    # MCap / cum TWh and MCap / days need complete history — merge from complete rebuild
    return out


def ratios_from_complete() -> pd.DataFrame:
    c = pd.read_csv(COMPLETE, parse_dates=["Date"]).sort_values("Date").reset_index(drop=True)
    daily_kwh = c["Energy_TWh_Annual"].astype(float) * 1e9 / 365.0
    c["cum_kwh"] = daily_kwh.cumsum()
    c["cum_days"] = np.arange(1, len(c) + 1, dtype=float)
    c["ratio_ceir"] = c["Market_Cap"].astype(float) / c["cumulative_cost"].astype(float)
    c["ratio_twh"] = c["Market_Cap"].astype(float) / c["cum_kwh"]
    c["ratio_days"] = c["Market_Cap"].astype(float) / c["cum_days"]
    for col in ["ratio_ceir", "ratio_twh", "ratio_days"]:
        c[f"log_{col}"] = np.log(c[col])
    return c


def fit(df: pd.DataFrame, y: str, x: str, *, min_n: int = 20, maxlags: int = 30) -> dict:
    s = df.dropna(subset=[y, x, "fear_greed_index", "Returns"]).copy()
    if len(s) < min_n:
        return {"n": len(s)}
    s["x_w"] = mstats.winsorize(s[x].astype(float), limits=[0.01, 0.01])
    s["trend"] = np.arange(len(s), dtype=float)
    fg = s["fear_greed_index"].astype(float)
    s["fg"] = (fg - fg.mean()) / (fg.std() or 1.0)
    # vol30 must be computed on the parent daily series before thinning
    if "vol30" not in s.columns or s["vol30"].isna().all():
        s["vol30"] = s["Returns"].astype(float).rolling(30, min_periods=10).std()
    s = s.dropna(subset=[y, "x_w", "trend", "fg", "vol30"])
    if len(s) < min_n:
        return {"n": len(s)}
    form = f"{y} ~ x_w + trend + fg + vol30"
    lags = min(maxlags, max(1, len(s) // 3))
    hac = smf.ols(form, data=s).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return {
        "n": len(s),
        "coef": float(hac.params["x_w"]),
        "p_hac": float(hac.pvalues["x_w"]),
        "adj_r2": float(hac.rsquared_adj),
    }


def main() -> int:
    panel = pd.read_csv(PANEL, parse_dates=["Date"])
    ratios = ratios_from_complete()
    df = panel.merge(
        ratios[["Date", "log_ratio_ceir", "log_ratio_twh", "log_ratio_days", "ratio_ceir", "ratio_twh", "ratio_days"]],
        on="Date",
        how="left",
    )
    df = prepare(df)
    # controls
    df["trend"] = np.arange(len(df), dtype=float)
    fg = df["fear_greed_index"].astype(float)
    df["fg"] = (fg - fg.mean()) / fg.std()
    df["vol30"] = df["Returns"].astype(float).rolling(30).std()

    # Precompute vol on full daily panel so thinned samples keep usable vol
    df["vol30"] = df["Returns"].astype(float).rolling(30, min_periods=10).std()

    pre = df[df["Date"] < CHINA_BAN].copy()
    post = df[df["Date"] >= CHINA_BAN].copy()

    def nonoverlap_within(sub: pd.DataFrame) -> pd.DataFrame:
        """Every 30th valid ret_30d observation *within* the regime."""
        out = sub.copy()
        out["ret_30d_nonoverlap"] = np.nan
        valid_idx = out.index[out["ret_30d"].notna()]
        keep = valid_idx[::30]
        out.loc[keep, "ret_30d_nonoverlap"] = out.loc[keep, "ret_30d"]
        return out

    pre_no = nonoverlap_within(pre)
    post_no = nonoverlap_within(post)
    full_no = nonoverlap_within(df)

    rows = []
    for regime, sub_daily, sub_no in [
        ("pre_ban", pre, pre_no),
        ("post_ban", post, post_no),
        ("full", df, full_no),
    ]:
        for y, sub in [
            ("ret_30d", sub_daily),
            ("ret_30d_nonoverlap", sub_no),
            ("ret_1m", sub_daily),
        ]:
            for x, label in [
                ("log_ratio_ceir", "CEIR"),
                ("log_ratio_twh", "MCap_over_cum_TWh"),
                ("log_ratio_days", "MCap_over_cum_days"),
            ]:
                r = fit(sub, y, x, min_n=15 if y != "ret_30d" else 40)
                rows.append({"regime": regime, "outcome": y, "regressor": label, **r})

    out = pd.DataFrame(rows)
    out.to_csv(OUT_CSV, index=False)

    # stationarity / cointegration on full analysis sample
    a = df.copy()
    a["log_mcap"] = np.log(a["Market_Cap"].astype(float))
    a["log_price"] = np.log(a["Price"].astype(float))
    a["log_cum_cost"] = np.log(a["cumulative_cost"].astype(float))
    a = a.merge(ratios[["Date", "cum_kwh", "cum_days"]], on="Date", how="left")
    a["log_cum_twh"] = np.log(a["cum_kwh"].astype(float))
    a["log_cum_days"] = np.log(a["cum_days"].astype(float))
    a = a.dropna(subset=["log_CEIR", "log_price", "log_mcap", "log_cum_cost", "log_cum_twh"]).copy()

    stat = {
        "adf_p_log_CEIR": adf_p(a["log_CEIR"]),
        "adf_p_log_mcap": adf_p(a["log_mcap"]),
        "adf_p_log_cum_cost": adf_p(a["log_cum_cost"]),
        "adf_p_log_cum_twh": adf_p(a["log_cum_twh"]),
        "adf_p_log_price": adf_p(a["log_price"]),
        "adf_p_ret_30d": adf_p(a["ret_30d"]),
        "corr_log_ceir_log_twh_ratio": float(a["log_ratio_ceir"].corr(a["log_ratio_twh"])),
        "corr_log_ceir_log_days_ratio": float(a["log_ratio_ceir"].corr(a["log_ratio_days"])),
    }
    try:
        stat["coint_p_mcap_cum_cost"] = float(coint(a["log_mcap"], a["log_cum_cost"])[1])
        stat["coint_p_mcap_cum_twh"] = float(coint(a["log_mcap"], a["log_cum_twh"])[1])
    except Exception as e:
        stat["coint_error"] = str(e)

    # pull prior pass-2 highlights
    joint = (RESULTS / "ceir_joint_break_wald.json").read_text(encoding="utf-8") if (RESULTS / "ceir_joint_break_wald.json").exists() else "{}"
    seed = (RESULTS / "ceir_cumulative_seed_audit.json").read_text(encoding="utf-8") if (RESULTS / "ceir_cumulative_seed_audit.json").exists() else "{}"

    def row(regime: str, outcome: str, regressor: str):
        hit = out[(out.regime == regime) & (out.outcome == outcome) & (out.regressor == regressor)]
        return hit.iloc[0] if len(hit) else None

    pre_ceir = row("pre_ban", "ret_30d", "CEIR")
    pre_twh = row("pre_ban", "ret_30d", "MCap_over_cum_TWh")
    pre_days = row("pre_ban", "ret_30d", "MCap_over_cum_days")
    pre_no = row("pre_ban", "ret_30d_nonoverlap", "CEIR")
    pre_m = row("pre_ban", "ret_1m", "CEIR")
    coint_cost = stat.get("coint_p_mcap_cum_cost")
    coint_twh = stat.get("coint_p_mcap_cum_twh")

    md = f"""# CEIR Final Diagnosis

**Date:** 2026-07-10  
**Purpose:** Close the CEIR investigation. Do **not** rescue an energy-specific coefficient.  
**Companion CSV:** `empirical_results/ceir_final_negative_controls.csv`  
**Reproduce:** `python3 thesis_package/ceir_final_diagnostics.py`

## Verdict

> Passive mining-cost ratios do **not** cleanly identify an energy-value anchor.

Apparent CEIR–return association in the legacy panel is **not distinguishable** from persistent valuation relative to a slowly rising denominator (cumulative energy quantity or even cumulative calendar time). Electricity-price construction in the canonical panel is defective; the 2018 cumulative-cost stock matters; robust joint break evidence is insignificant; trading underperforms.

**Chapter 3 role going forward:** boundary / negative identification diagnosis that motivates explicit constraints (Chapters 4–5).

## Stationarity and common-trend diagnostics

| Series | ADF p-value (lower ⇒ more evidence against unit root) |
|--------|------------------------------------------------------:|
| log(CEIR) | {stat['adf_p_log_CEIR']:.4g} |
| log(MarketCap) | {stat['adf_p_log_mcap']:.4g} |
| log(cumulative cost) | {stat['adf_p_log_cum_cost']:.4g} |
| log(cumulative TWh) | {stat['adf_p_log_cum_twh']:.4g} |
| log(Price) | {stat['adf_p_log_price']:.4g} |
| ret_30d | {stat['adf_p_ret_30d']:.4g} |

| Pair | Corr of log ratios |
|------|-------------------:|
| CEIR vs MCap/cum TWh | {stat['corr_log_ceir_log_twh_ratio']:.6f} |
| CEIR vs MCap/cum days | {stat['corr_log_ceir_log_days_ratio']:.4f} |

| Cointegration (Engle–Granger) | p-value |
|-------------------------------|--------:|
| log(MCap) ~ log(cum cost) | {coint_cost:.4f} |
| log(MCap) ~ log(cum TWh) | {coint_twh:.4f} |

**Reading:** CEIR and MCap/cum-TWh log-ratios are essentially the same object under the legacy near-constant tariff (corr ≈ 1). That alone ends any claim that geography-weighted electricity pricing drives the result. Engle–Granger cointegration does not support a stable long-run MCap–cost equilibrium in this panel.

## Negative-control comparison

### Preferred overlapping 30-day returns (pre-ban)

| Regressor | β | HAC p | N |
|-----------|--:|------:|--:|
| CEIR | {pre_ceir.coef:.4f} | {pre_ceir.p_hac:.4g} | {int(pre_ceir.n)} |
| MCap / cum TWh | {pre_twh.coef:.4f} | {pre_twh.p_hac:.4g} | {int(pre_twh.n)} |
| MCap / cum days | {pre_days.coef:.4f} | {pre_days.p_hac:.4g} | {int(pre_days.n)} |

### Non-overlapping 30-day and monthly (pre-ban; small N — interpretive only)

| Spec | β (CEIR) | HAC p | N |
|------|---------:|------:|--:|
| Non-overlapping 30d | {pre_no.coef:.4f} | {pre_no.p_hac:.4g} | {int(pre_no.n)} |
| Month-end → next month | {pre_m.coef:.4f} | {pre_m.p_hac:.4g} | {int(pre_m.n)} |

**Caveat:** Thinned samples remain numerically close across CEIR / TWh / days. They do **not** restore an electricity-price-specific identification. Post-ban overlapping 30d CEIR remains weak (β ≈ −0.07, HAC p ≈ 0.13). Full table: `ceir_final_negative_controls.csv`.

## Prior audit facts retained

1. Legacy `electricity_price` ≈ constant 0.076 with 29 month-start spikes (failed merge) — see `CEIR_DATA_LINEAGE_AUDIT.md`.  
2. ~$3.30bn on 2019-01-01 = 2018 cumsum under that constant (`ceir_cumulative_seed_audit.json`).  
3. Uniform ±20% price scaling is a mathematical identity under constant p, not robustness.  
4. Regime horse races with price/momentum are collinear/unstable (sign flips).  
5. Joint robust Wald on full post-ban interactions: HAC p ≈ 0.13 (does **not** reject stability).  
6. Trading rule underperforms buy-and-hold (+176% vs +2771%).

## What this does **not** kill

- Energy expenditure in Bitcoin mining is real.  
- The five-constraint architecture (data, issuance, pricing, settlement, governance).  
- Public Lab issuance/settlement demonstration on Sepolia.

## What this does kill / retire

- CEIR as a clean energy-specific valuation factor.  
- China ban as a strongly identified structural break under robust joint tests.  
- “Canonical weighted electricity-cost denominator” as currently stored.  
- Any bridge that says CEIR validates SolarPunk issuance.

## Stop rule

No further CEIR coefficient hunting. Optional later work is only documentation hygiene or a fully rebuilt panel for appendix transparency — not thesis-centre rescue.
"""
    OUT_MD.write_text(md, encoding="utf-8")
    print(out.to_string(index=False))
    print(stat)
    print(f"wrote {OUT_CSV}")
    print(f"wrote {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
