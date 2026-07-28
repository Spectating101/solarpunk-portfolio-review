#!/usr/bin/env python3
"""
Thesis v11 CEIR hardening: cost sensitivity, break interaction, incremental info.

Does not rewrite the thesis. Writes CSVs + notes under thesis_package/.
Reports unstable results honestly.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import f as f_dist
from scipy.stats import mstats

PKG = Path(__file__).resolve().parent
RESULTS = PKG / "empirical_results"
COMPLETE = RESULTS / "bitcoin_ceir_complete.csv"
PANEL = RESULTS / "bitcoin_ceir_analysis_ready.csv"
MONTHLY = PKG.parent / "empirical" / "weighted_electricity_prices_monthly.csv"
ETH_GRANT = PKG.parent / "empirical" / "ETH-grant" / "bitcoin_ceir_full.csv"

CHINA_BAN = pd.Timestamp("2021-06-20")
CAMBRIDGE_END = pd.Timestamp("2022-01-01")
LEVEL_FORMULA = "ret_30d ~ log_ceir_w + trend + fg + vol30"


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    out = df.sort_values("Date").reset_index(drop=True).copy()
    if "in_analysis_period" in out.columns:
        out = out[out["in_analysis_period"] == 1].copy()
    out["ret_30d"] = out["Price"].shift(-30) / out["Price"] - 1
    out["log_ceir_w"] = mstats.winsorize(out["log_CEIR"].astype(float), limits=[0.01, 0.01])
    out["trend"] = np.arange(len(out))
    fg = out["fear_greed_index"].astype(float)
    out["fg"] = (fg - fg.mean()) / fg.std()
    out["vol30"] = out["Returns"].rolling(30).std()
    out["month"] = out["Date"].dt.to_period("M").astype(str)
    out["post_ban"] = (out["Date"] >= CHINA_BAN).astype(int)
    out["log_ceir_x_post"] = out["log_ceir_w"] * out["post_ban"]
    # incremental-info features
    out["log_price"] = np.log(out["Price"].astype(float))
    out["log_mcap"] = np.log(out["Market_Cap"].astype(float))
    out["ret_trail_30"] = out["Price"] / out["Price"].shift(30) - 1
    out["ret_trail_180"] = out["Price"] / out["Price"].shift(180) - 1
    roll = out["Price"].rolling(180, min_periods=60).mean()
    out["price_to_trend"] = out["Price"] / roll - 1
    return out


def _fit_period(sub: pd.DataFrame, formula: str, regressor: str) -> dict:
    need = ["ret_30d", "month"] + [
        c for c in ["log_ceir_w", "trend", "fg", "vol30", "post_ban", "log_ceir_x_post",
                    "log_price", "log_mcap", "ret_trail_30", "ret_trail_180", "price_to_trend"]
        if c in formula
    ]
    s = sub.dropna(subset=[c for c in need if c in sub.columns]).copy()
    if len(s) < 50:
        return {"n": len(s), "beta": np.nan, "p_hac": np.nan, "p_cluster": np.nan, "se_hac": np.nan}
    hac = smf.ols(formula, data=s).fit(cov_type="HAC", cov_kwds={"maxlags": 30})
    cl = smf.ols(formula, data=s).fit(cov_type="cluster", cov_kwds={"groups": s["month"]})
    return {
        "n": len(s),
        "beta": float(hac.params[regressor]),
        "p_hac": float(hac.pvalues[regressor]),
        "p_cluster": float(cl.pvalues[regressor]),
        "se_hac": float(hac.bse[regressor]),
        "adj_r2": float(hac.rsquared_adj),
    }


def _chow(pre: pd.DataFrame, post: pd.DataFrame, formula: str) -> float:
    cols = ["ret_30d"] + [c for c in ["log_ceir_w", "trend", "fg", "vol30"] if c in formula]
    s1 = pre.dropna(subset=cols)
    s2 = post.dropna(subset=cols)
    comb = pd.concat([s1, s2])
    pooled = smf.ols(formula, data=comb).fit()
    r1 = smf.ols(formula, data=s1).fit()
    r2 = smf.ols(formula, data=s2).fit()
    k = len(pooled.params)
    n1, n2 = len(s1), len(s2)
    num = (pooled.ssr - (r1.ssr + r2.ssr)) / k
    den = (r1.ssr + r2.ssr) / (n1 + n2 - 2 * k)
    f_stat = num / den if den > 0 else np.nan
    return float(1 - f_dist.cdf(f_stat, k, n1 + n2 - 2 * k))


def split_summary(df: pd.DataFrame, variant: str, note: str = "") -> dict:
    pre = df[df["Date"] < CHINA_BAN]
    post = df[df["Date"] >= CHINA_BAN]
    pre_r = _fit_period(pre, LEVEL_FORMULA, "log_ceir_w")
    post_r = _fit_period(post, LEVEL_FORMULA, "log_ceir_w")
    chow = _chow(pre, post, LEVEL_FORMULA)
    s_pre = pre.dropna(subset=["ret_30d", "log_ceir_w", "trend", "fg", "vol30"])
    econ = float(s_pre["log_ceir_w"].std() * pre_r["beta"] * 100) if len(s_pre) else np.nan
    return {
        "variant": variant,
        "note": note,
        "pre_ban_coef": pre_r["beta"],
        "post_ban_coef": post_r["beta"],
        "pre_ban_p_hac": pre_r["p_hac"],
        "post_ban_p_hac": post_r["p_hac"],
        "pre_ban_p_cluster": pre_r["p_cluster"],
        "post_ban_p_cluster": post_r["p_cluster"],
        "chow_pvalue": chow,
        "econ_impact_1sd_30d_pct": econ,
        "pre_ban_n": pre_r["n"],
        "post_ban_n": post_r["n"],
        "sample_start": str(df["Date"].min().date()),
        "sample_end": str(df["Date"].max().date()),
    }


def rebuild_ceir_from_prices(complete: pd.DataFrame, price: pd.Series) -> pd.DataFrame:
    """Rebuild daily_cost, cumulative_cost, CEIR, log_CEIR from a price series aligned to complete."""
    out = complete.sort_values("Date").reset_index(drop=True).copy()
    p = price.reindex(out.index).astype(float)
    daily_kwh = out["Energy_TWh_Annual"].astype(float) * 1e9 / 365.0
    out["electricity_price"] = p.values
    out["daily_cost_usd"] = daily_kwh * p.values
    out["cumulative_cost"] = out["daily_cost_usd"].cumsum()
    out["CEIR"] = out["Market_Cap"].astype(float) / out["cumulative_cost"]
    out["log_CEIR"] = np.log(out["CEIR"])
    return out


def monthly_ffill_prices(complete: pd.DataFrame) -> pd.Series:
    """Closest intended construction: monthly weighted prices → daily ffill → freeze last."""
    monthly = pd.read_csv(MONTHLY, parse_dates=["date"]).sort_values("date")
    idx = complete.sort_values("Date")["Date"]
    s = pd.Series(index=pd.DatetimeIndex(idx), dtype=float)
    for _, row in monthly.iterrows():
        s.loc[row["date"]] = float(row["weighted_price"])
    # also set month-starts that match
    s = s.copy()
    s = s.ffill().bfill()
    # After last Cambridge month, freeze last observed weighted price
    last = float(monthly["weighted_price"].iloc[-1])
    s.loc[s.index > CAMBRIDGE_END] = last
    # Before first month, use first
    first = float(monthly["weighted_price"].iloc[0])
    s.loc[s.index < monthly["date"].iloc[0]] = first
    return pd.Series(s.values, index=np.arange(len(s)))


def eth_grant_prices(complete: pd.DataFrame) -> pd.Series:
    eth = pd.read_csv(ETH_GRANT, parse_dates=["Date"]).sort_values("Date")
    merged = complete.sort_values("Date")[["Date"]].merge(
        eth[["Date", "electricity_price"]], on="Date", how="left"
    )
    return merged["electricity_price"].astype(float)


def run_cost_sensitivity() -> pd.DataFrame:
    complete = pd.read_csv(COMPLETE, parse_dates=["Date"])
    baseline_panel = _prepare(pd.read_csv(PANEL, parse_dates=["Date"]))
    rows = []

    # A. Current baseline panel
    rows.append(split_summary(baseline_panel, "A_baseline", "Canonical analysis_ready panel as stored"))

    # B/C. ±20% on stored prices, rebuild cumulative from complete start
    for label, scale in [("B_price_minus_20pct", 0.8), ("C_price_plus_20pct", 1.2)]:
        scaled = complete["electricity_price"].astype(float) * scale
        rebuilt = rebuild_ceir_from_prices(complete, scaled)
        ready = rebuilt[rebuilt["Date"] >= "2019-01-01"].copy()
        ready["in_analysis_period"] = 1
        # keep fear/greed from complete
        rows.append(
            split_summary(
                _prepare(ready),
                label,
                "Scale stored electricity_price then rebuild cumulative; near-constant p ⇒ log CEIR shifts ≈ constant (β largely unchanged)",
            )
        )

    # D. Restricted to last Cambridge geography date
    raw = pd.read_csv(PANEL, parse_dates=["Date"])
    raw_d = raw[raw["Date"] <= CAMBRIDGE_END].copy()
    rows.append(
        split_summary(
            _prepare(raw_d),
            "D_end_at_cambridge_geography",
            f"Sample ends {CAMBRIDGE_END.date()} (last Cambridge mining-map month)",
        )
    )

    # E. Alternative post-2022: monthly ffill + freeze last Cambridge weight
    tv = monthly_ffill_prices(complete)
    rebuilt_tv = rebuild_ceir_from_prices(complete, tv)
    ready_tv = rebuilt_tv[rebuilt_tv["Date"] >= "2019-01-01"].copy()
    ready_tv["fear_greed_index"] = complete.loc[complete["Date"] >= "2019-01-01", "fear_greed_index"].values
    ready_tv["Returns"] = complete.loc[complete["Date"] >= "2019-01-01", "Returns"].values
    ready_tv["in_analysis_period"] = 1
    rows.append(
        split_summary(
            _prepare(ready_tv),
            "E_monthly_ffill_freeze_last",
            "Rebuild with weighted_electricity_prices_monthly ffill; freeze Jan-2022 weight thereafter",
        )
    )

    # E2. ETH-grant annual constants post-2022
    if ETH_GRANT.exists():
        eth_p = eth_grant_prices(complete)
        rebuilt_e = rebuild_ceir_from_prices(complete, eth_p)
        ready_e = rebuilt_e[rebuilt_e["Date"] >= "2019-01-01"].copy()
        ready_e["fear_greed_index"] = complete.loc[complete["Date"] >= "2019-01-01", "fear_greed_index"].values
        ready_e["Returns"] = complete.loc[complete["Date"] >= "2019-01-01", "Returns"].values
        ready_e["in_analysis_period"] = 1
        rows.append(
            split_summary(
                _prepare(ready_e),
                "E2_eth_grant_price_path",
                "Orphan ETH-grant electricity_price path (monthly then annual constants)",
            )
        )

    # Time-varying ±20% (meaningful sensitivity)
    for label, scale in [("E_tv_price_minus_20pct", 0.8), ("E_tv_price_plus_20pct", 1.2)]:
        rebuilt = rebuild_ceir_from_prices(complete, tv * scale)
        ready = rebuilt[rebuilt["Date"] >= "2019-01-01"].copy()
        ready["fear_greed_index"] = complete.loc[complete["Date"] >= "2019-01-01", "fear_greed_index"].values
        ready["Returns"] = complete.loc[complete["Date"] >= "2019-01-01", "Returns"].values
        ready["in_analysis_period"] = 1
        rows.append(
            split_summary(
                _prepare(ready),
                label,
                "±20% on time-varying monthly-ffill price path (not constant panel default)",
            )
        )

    return pd.DataFrame(rows)


def run_break_interaction(df: pd.DataFrame) -> pd.DataFrame:
    """Pooled interaction: ret ~ log_ceir + post_ban + log_ceir×post_ban + controls."""
    formula = "ret_30d ~ log_ceir_w + post_ban + log_ceir_x_post + trend + fg + vol30"
    formula_full = (
        "ret_30d ~ log_ceir_w + post_ban + log_ceir_x_post + trend + fg + vol30 "
        "+ post_ban:trend + post_ban:fg + post_ban:vol30"
    )
    cols = ["ret_30d", "log_ceir_w", "post_ban", "log_ceir_x_post", "trend", "fg", "vol30", "month"]
    s = df.dropna(subset=cols).copy()
    rows = []
    for name, form in [("interaction_core", formula), ("interaction_full_controls", formula_full)]:
        hac = smf.ols(form, data=s).fit(cov_type="HAC", cov_kwds={"maxlags": 30})
        cl = smf.ols(form, data=s).fit(cov_type="cluster", cov_kwds={"groups": s["month"]})
        rows.append(
            {
                "spec": name,
                "n": len(s),
                "beta_log_ceir": float(hac.params["log_ceir_w"]),
                "beta_post_ban": float(hac.params["post_ban"]),
                "beta3_interaction": float(hac.params["log_ceir_x_post"]),
                "p_hac_beta3": float(hac.pvalues["log_ceir_x_post"]),
                "p_cluster_beta3": float(cl.pvalues["log_ceir_x_post"]),
                "p_hac_log_ceir": float(hac.pvalues["log_ceir_w"]),
                "p_cluster_log_ceir": float(cl.pvalues["log_ceir_w"]),
                "adj_r2": float(hac.rsquared_adj),
            }
        )
    # supplementary classical Chow on preferred split
    pre = df[df["Date"] < CHINA_BAN]
    post = df[df["Date"] >= CHINA_BAN]
    rows.append(
        {
            "spec": "supplementary_chow_level_split",
            "n": int(len(pre.dropna(subset=["ret_30d", "log_ceir_w"])) + len(post.dropna(subset=["ret_30d", "log_ceir_w"]))),
            "beta_log_ceir": np.nan,
            "beta_post_ban": np.nan,
            "beta3_interaction": np.nan,
            "p_hac_beta3": _chow(pre, post, LEVEL_FORMULA),
            "p_cluster_beta3": np.nan,
            "p_hac_log_ceir": np.nan,
            "p_cluster_log_ceir": np.nan,
            "adj_r2": np.nan,
            "note": "p_hac_beta3 column holds classical Chow p-value for supplementary reporting",
        }
    )
    return pd.DataFrame(rows)


def run_incremental(df: pd.DataFrame) -> pd.DataFrame:
    specs = [
        ("ceir_only_preferred", LEVEL_FORMULA, "log_ceir_w"),
        (
            "benchmark_only",
            "ret_30d ~ log_price + ret_trail_30 + ret_trail_180 + vol30 + fg + price_to_trend + trend",
            "log_price",
        ),
        (
            "ceir_plus_benchmark",
            "ret_30d ~ log_ceir_w + log_price + ret_trail_30 + ret_trail_180 + vol30 + fg + price_to_trend + trend",
            "log_ceir_w",
        ),
        (
            "ceir_plus_mcap_momentum",
            "ret_30d ~ log_ceir_w + log_mcap + ret_trail_30 + ret_trail_180 + vol30 + fg + trend",
            "log_ceir_w",
        ),
    ]
    rows = []
    for name, formula, focus in specs:
        need = ["ret_30d", "month"] + [
            t
            for t in formula.replace("~", " ").replace("+", " ").split()
            if t not in {"ret_30d", ""}
        ]
        s = df.dropna(subset=[c for c in need if c in df.columns]).copy()
        if len(s) < 100:
            continue
        hac = smf.ols(formula, data=s).fit(cov_type="HAC", cov_kwds={"maxlags": 30})
        cl = smf.ols(formula, data=s).fit(cov_type="cluster", cov_kwds={"groups": s["month"]})
        row = {
            "model": name,
            "n": len(s),
            "focus_regressor": focus,
            "focus_coef": float(hac.params[focus]),
            "focus_p_hac": float(hac.pvalues[focus]),
            "focus_p_cluster": float(cl.pvalues[focus]),
            "adj_r2": float(hac.rsquared_adj),
            "sample_start": str(s["Date"].min().date()),
            "sample_end": str(s["Date"].max().date()),
        }
        if "log_ceir_w" in hac.params:
            row["ceir_coef"] = float(hac.params["log_ceir_w"])
            row["ceir_p_hac"] = float(hac.pvalues["log_ceir_w"])
            row["ceir_p_cluster"] = float(cl.pvalues["log_ceir_w"])
        else:
            row["ceir_coef"] = np.nan
            row["ceir_p_hac"] = np.nan
            row["ceir_p_cluster"] = np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def write_notes(sens: pd.DataFrame, brk: pd.DataFrame, inc: pd.DataFrame) -> None:
    a = sens[sens.variant == "A_baseline"].iloc[0]
    core = brk[brk.spec == "interaction_core"].iloc[0]
    full = brk[brk.spec == "interaction_full_controls"].iloc[0]
    ceir_plus = inc[inc.model == "ceir_plus_benchmark"].iloc[0]
    ceir_only = inc[inc.model == "ceir_only_preferred"].iloc[0]

    # Interaction language recommendation
    sig_hac = core["p_hac_beta3"] < 0.05
    sig_cl = core["p_cluster_beta3"] < 0.05
    if sig_hac and sig_cl:
        break_lang = "strong evidence of parameter instability"
    elif sig_hac or sig_cl:
        break_lang = "suggestive evidence of parameter instability"
    else:
        break_lang = "remove strong structural-break language; treat break as weak/inconclusive under robust SEs"

    ceir_keeps = (ceir_plus["ceir_p_hac"] < 0.10) or (ceir_plus["ceir_p_cluster"] < 0.10)

    (PKG / "CEIR_COST_SENSITIVITY_NOTES.md").write_text(
        f"""# CEIR Cost Sensitivity Notes (v11)

**Generated by:** `thesis_package/ceir_v11_robustness.py`  
**Companion CSV:** `empirical_results/ceir_cost_sensitivity.csv`

## Baseline (A)

| Item | Value |
|------|------:|
| Pre-ban β | {a.pre_ban_coef:.4f} |
| Post-ban β | {a.post_ban_coef:.4f} |
| Pre HAC p | {a.pre_ban_p_hac:.4g} |
| Post HAC p | {a.post_ban_p_hac:.4g} |
| Chow p | {a.chow_pvalue:.2e} |

## Important construction caveat

The canonical panel `electricity_price` is **near-constant** (~0.076 $/kWh) with 29 unfilled month-start spikes (see `CEIR_DATA_LINEAGE_AUDIT.md`).

Therefore variants **B/C** (scale stored prices ±20% and rebuild cumulative) mostly **shift log(CEIR) by a near-constant**. In a regression with an intercept, **β on log(CEIR) is essentially unchanged**. That is **not** evidence of cost robustness — it is a mechanical consequence of constant prices.

Meaningful cost sensitivity is in **E / E_tv_±20%** (time-varying monthly-ffill path) and **E2** (ETH-grant path).

## Do not claim robustness if…

Compare pre/post coefficients and p-values across A, D, E, E2, and E_tv_±20% in the CSV. If signs flip, magnitudes move sharply, or significance disappears under time-varying costs or the Cambridge-end sample, state that honestly in Chapter 3.

## Restricted geography sample (D)

Ending at {CAMBRIDGE_END.date()} removes post-map years where geography is unavailable. Prefer this as a **boundary sample**, not as the only reported result.
""",
        encoding="utf-8",
    )

    (PKG / "CEIR_INCREMENTAL_INFORMATION_NOTES.md").write_text(
        f"""# CEIR Incremental Information Notes (v11)

**Generated by:** `thesis_package/ceir_v11_robustness.py`  
**Companion CSV:** `empirical_results/ceir_incremental_information.csv`

## Question

Does CEIR add explanatory content for 30-day forward returns beyond generic Bitcoin valuation / return dynamics?

## Headline comparison

| Model | Focus | coef | HAC p | cluster p | adj R² | N |
|-------|-------|-----:|------:|----------:|------:|--:|
| CEIR-only preferred | log_ceir_w | {ceir_only.focus_coef:.4f} | {ceir_only.focus_p_hac:.4g} | {ceir_only.focus_p_cluster:.4g} | {ceir_only.adj_r2:.4f} | {int(ceir_only.n)} |
| CEIR + benchmark | log_ceir_w | {ceir_plus.ceir_coef:.4f} | {ceir_plus.ceir_p_hac:.4g} | {ceir_plus.ceir_p_cluster:.4g} | {ceir_plus.adj_r2:.4f} | {int(ceir_plus.n)} |

## Interpretation rule (do not force energy-specific claim)

- If CEIR remains significant (or marginally so) after price/momentum/vol/fear-greed/trend controls: may claim **incremental association**, not identification of an energy channel.
- If CEIR loses significance: **do not** claim an energy-specific pricing channel. Frame Chapter 3 as exploratory / boundary evidence that motivates explicit constraints (Ch 4–5).

**Current automated reading:** CEIR {"retains" if ceir_keeps else "does not retain"} incremental content at the 10% level under HAC or clustered SEs in the CEIR+benchmark horse race.

## Break-interaction language (Task 3)

Core interaction β3 HAC p={core.p_hac_beta3:.4g}, cluster p={core.p_cluster_beta3:.4g}.  
Full-controls interaction β3 HAC p={full.p_hac_beta3:.4g}, cluster p={full.p_cluster_beta3:.4g}.

**Recommended Chapter 3 wording:** {break_lang}.
""",
        encoding="utf-8",
    )


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    sens = run_cost_sensitivity()
    sens_path = RESULTS / "ceir_cost_sensitivity.csv"
    sens.to_csv(sens_path, index=False)

    baseline = _prepare(pd.read_csv(PANEL, parse_dates=["Date"]))
    brk = run_break_interaction(baseline)
    brk_path = RESULTS / "ceir_break_interaction.csv"
    brk.to_csv(brk_path, index=False)

    inc = run_incremental(baseline)
    inc_path = RESULTS / "ceir_incremental_information.csv"
    inc.to_csv(inc_path, index=False)

    write_notes(sens, brk, inc)

    print(f"wrote {sens_path}")
    print(f"wrote {brk_path}")
    print(f"wrote {inc_path}")
    print(f"wrote {PKG / 'CEIR_COST_SENSITIVITY_NOTES.md'}")
    print(f"wrote {PKG / 'CEIR_INCREMENTAL_INFORMATION_NOTES.md'}")
    print(sens[["variant", "pre_ban_coef", "post_ban_coef", "pre_ban_p_hac", "post_ban_p_hac", "chow_pvalue"]].to_string(index=False))
    print("--- interaction ---")
    print(brk.to_string(index=False))
    print("--- incremental ---")
    print(inc.to_string(index=False))
    print("ceir_v11_robustness_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
