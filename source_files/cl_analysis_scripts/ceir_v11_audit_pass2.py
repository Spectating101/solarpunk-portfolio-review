#!/usr/bin/env python3
"""
CEIR audit pass 2 (Sol correction) — no manuscript / no v11.

Adds:
- documented 2018→2019 cumulative seed
- regime-specific incremental-information tests + Wald
- joint robust Wald on full post-ban interactions
- economically distinct denominator constructions
- benchmark ratios (MCap/TWh, MCap/time)

Does NOT overwrite bitcoin_ceir_analysis_ready.csv.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy.stats import mstats

PKG = Path(__file__).resolve().parent
ROOT = PKG.parent
RESULTS = PKG / "empirical_results"
EMP = ROOT / "empirical"
COMPLETE = RESULTS / "bitcoin_ceir_complete.csv"
PANEL = RESULTS / "bitcoin_ceir_analysis_ready.csv"
GEO = EMP / "cambridge_mining_distribution.csv"
MONTHLY = EMP / "weighted_electricity_prices_monthly.csv"

CHINA_BAN = pd.Timestamp("2021-06-20")
CAMBRIDGE_END = pd.Timestamp("2022-01-01")

# Competing country-price vectors (from repo scripts)
PRICE_CAMBRIDGE = {
    "china": 0.040,
    "usa": 0.065,
    "russia": 0.050,
    "kazakhstan": 0.045,
    "canada": 0.070,
    "malaysia": 0.055,
    "iran": 0.035,
    "others": 0.060,
}
PRICE_DATAGATH = {
    "china": 0.080,
    "usa": 0.068,
    "russia": 0.044,
    "kazakhstan": 0.038,
    "canada": 0.061,
    "malaysia": 0.077,
    "iran": 0.007,
    "others": 0.065,
}
PRICE_FUSION = {
    "china": 0.088,
    "usa": 0.147,
    "russia": 0.090,
    "kazakhstan": 0.074,
    "canada": 0.107,
    "malaysia": 0.134,
    "iran": 0.040,
    "others": 0.120,
}


def load_complete() -> pd.DataFrame:
    return pd.read_csv(COMPLETE, parse_dates=["Date"]).sort_values("Date").reset_index(drop=True)


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    out = df.sort_values("Date").reset_index(drop=True).copy()
    if "in_analysis_period" in out.columns:
        out = out[out["in_analysis_period"] == 1].copy()
    out["ret_30d"] = out["Price"].astype(float).shift(-30) / out["Price"].astype(float) - 1
    out["log_ceir_w"] = mstats.winsorize(out["log_CEIR"].astype(float), limits=[0.01, 0.01])
    out["trend"] = np.arange(len(out), dtype=float)
    fg = out["fear_greed_index"].astype(float)
    out["fg"] = (fg - fg.mean()) / fg.std()
    out["vol30"] = out["Returns"].astype(float).rolling(30).std()
    out["month"] = out["Date"].dt.to_period("M").astype(str)
    out["post_ban"] = (out["Date"] >= CHINA_BAN).astype(int)
    out["log_ceir_x_post"] = out["log_ceir_w"] * out["post_ban"]
    out["log_price"] = np.log(out["Price"].astype(float))
    out["log_mcap"] = np.log(out["Market_Cap"].astype(float))
    out["ret_trail_30"] = out["Price"].astype(float) / out["Price"].astype(float).shift(30) - 1
    out["ret_trail_180"] = out["Price"].astype(float) / out["Price"].astype(float).shift(180) - 1
    roll = out["Price"].astype(float).rolling(180, min_periods=60).mean()
    out["price_to_trend"] = out["Price"].astype(float) / roll - 1
    return out


def rebuild_from_price(complete: pd.DataFrame, price: pd.Series, *, seed_scale: float = 1.0) -> pd.DataFrame:
    """Rebuild CEIR from a daily price path. seed_scale multiplies 2018 costs only."""
    out = complete.sort_values("Date").reset_index(drop=True).copy()
    p = np.asarray(price, dtype=float)
    daily_kwh = out["Energy_TWh_Annual"].astype(float) * 1e9 / 365.0
    daily = daily_kwh * p
    # scale pre-2019 costs (the "seed" for analysis_ready)
    mask_2018 = out["Date"] < "2019-01-01"
    daily = daily.copy()
    daily[mask_2018] = daily[mask_2018] * seed_scale
    out["electricity_price"] = p
    out["daily_cost_usd"] = daily
    out["cumulative_cost"] = np.cumsum(daily)
    out["CEIR"] = out["Market_Cap"].astype(float) / out["cumulative_cost"]
    out["log_CEIR"] = np.log(out["CEIR"])
    return out


def geo_weighted_daily(complete: pd.DataFrame, price_vec: dict, *, post2022: str = "freeze") -> pd.Series:
    geo = pd.read_csv(GEO, parse_dates=["date"]).sort_values("date")
    countries = [c for c in geo.columns if c not in {"date"}]
    # map usa/us
    def price_for(country: str) -> float:
        if country in price_vec:
            return float(price_vec[country])
        if country == "usa" and "us" in price_vec:
            return float(price_vec["us"])
        if country == "us" and "usa" in price_vec:
            return float(price_vec["usa"])
        return float(price_vec.get("others", 0.06))

    monthly = []
    for _, row in geo.iterrows():
        wsum = 0.0
        p = 0.0
        for c in countries:
            w = float(row[c])
            if w <= 0:
                continue
            p += w * price_for(c)
            wsum += w
        if wsum < 0.99:
            p += (1.0 - wsum) * price_for("others")
        monthly.append((row["date"], p))
    mdf = pd.DataFrame(monthly, columns=["date", "p"]).sort_values("date")

    idx = complete["Date"]
    s = pd.Series(np.nan, index=np.arange(len(complete)))
    date_to_i = {d: i for i, d in enumerate(complete["Date"])}
    for _, row in mdf.iterrows():
        d = row["date"]
        if d in date_to_i:
            s.iloc[date_to_i[d]] = row["p"]
    # ffill/bfill within observed geography window
    s = s.ffill().bfill()
    last_p = float(mdf["p"].iloc[-1])
    first_p = float(mdf["p"].iloc[0])
    dates = complete["Date"]
    for i, d in enumerate(dates):
        if d < mdf["date"].iloc[0]:
            s.iloc[i] = first_p
        elif d > CAMBRIDGE_END:
            if post2022 == "freeze":
                s.iloc[i] = last_p
            elif post2022 == "us_dominant":
                s.iloc[i] = price_for("usa") * 1.15
            elif post2022 == "global_avg":
                s.iloc[i] = float(np.mean(list(price_vec.values())))
            else:
                s.iloc[i] = last_p
    return s


def fit_model(df: pd.DataFrame, formula: str, focus: str | None = None) -> dict:
    need = ["ret_30d", "month"] + [
        t for t in formula.replace("~", " ").replace("+", " ").replace(":", " ").split() if t not in {"ret_30d", ""}
    ]
    cols = [c for c in need if c in df.columns]
    s = df.dropna(subset=cols).copy()
    if len(s) < 80:
        return {"n": len(s), "error": "insufficient_n"}
    hac = smf.ols(formula, data=s).fit(cov_type="HAC", cov_kwds={"maxlags": 30})
    cl = smf.ols(formula, data=s).fit(cov_type="cluster", cov_kwds={"groups": s["month"]})
    out = {
        "n": len(s),
        "adj_r2": float(hac.rsquared_adj),
        "aic": float(hac.aic),
        "bic": float(hac.bic),
        "sample_start": str(s["Date"].min().date()),
        "sample_end": str(s["Date"].max().date()),
    }
    if focus and focus in hac.params:
        out["focus"] = focus
        out["coef"] = float(hac.params[focus])
        out["p_hac"] = float(hac.pvalues[focus])
        out["p_cluster"] = float(cl.pvalues[focus])
        # robust Wald for focus == 0
        try:
            w_hac = float(hac.wald_test(f"{focus} = 0", scalar=True).pvalue)
            w_cl = float(cl.wald_test(f"{focus} = 0", scalar=True).pvalue)
            out["wald_p_hac"] = w_hac
            out["wald_p_cluster"] = w_cl
        except Exception as e:
            out["wald_error"] = str(e)
    return out, hac, cl, s


def incremental_block(df: pd.DataFrame, label: str) -> list[dict]:
    rows = []
    ceir_only = "ret_30d ~ log_ceir_w + trend + fg + vol30"
    bench = "ret_30d ~ log_price + ret_trail_30 + ret_trail_180 + vol30 + fg + price_to_trend + trend"
    both = "ret_30d ~ log_ceir_w + log_price + ret_trail_30 + ret_trail_180 + vol30 + fg + price_to_trend + trend"
    for name, form, focus in [
        ("ceir_only", ceir_only, "log_ceir_w"),
        ("benchmark_only", bench, "log_price"),
        ("benchmark_plus_ceir", both, "log_ceir_w"),
    ]:
        res = fit_model(df, form, focus)
        if isinstance(res, tuple):
            row, hac, cl, s = res
        else:
            row = res
            rows.append({"regime": label, "model": name, **row})
            continue
        # incremental Wald: CEIR = 0 in the both model
        if name == "benchmark_plus_ceir":
            try:
                row["incremental_wald_p_hac"] = float(hac.wald_test("log_ceir_w = 0", scalar=True).pvalue)
                row["incremental_wald_p_cluster"] = float(cl.wald_test("log_ceir_w = 0", scalar=True).pvalue)
            except Exception as e:
                row["incremental_wald_error"] = str(e)
        rows.append({"regime": label, "model": name, **row})
    return rows


def joint_break_wald(df: pd.DataFrame) -> dict:
    # fully interacted controls
    form = (
        "ret_30d ~ log_ceir_w + post_ban + log_ceir_x_post + trend + fg + vol30 "
        "+ post_ban:trend + post_ban:fg + post_ban:vol30"
    )
    res = fit_model(df, form, "log_ceir_x_post")
    row, hac, cl, s = res
    # joint H0: all post interactions = 0
    hyp = "log_ceir_x_post = 0, post_ban:trend = 0, post_ban:fg = 0, post_ban:vol30 = 0"
    # statsmodels may name interactions differently
    names = list(hac.params.index)
    inter_names = [n for n in names if ("post_ban" in n and n != "post_ban") or n == "log_ceir_x_post"]
    # exclude main post_ban level from joint "slope change" set? Sol asked for interaction terms.
    # Include: log_ceir_x_post, post_ban:trend, post_ban:fg, post_ban:vol30
    targets = []
    for cand in ["log_ceir_x_post", "post_ban:trend", "post_ban:fg", "post_ban:vol30"]:
        if cand in names:
            targets.append(cand)
        else:
            # try alternate naming
            alt = [n for n in names if n.replace(" ", "") == cand.replace(" ", "")]
            targets.extend(alt)
    targets = sorted(set(targets))
    hyp = ", ".join(f"{t} = 0" for t in targets)
    out = {
        "n": row["n"],
        "interaction_terms_tested": targets,
        "single_beta3_coef": row.get("coef"),
        "single_beta3_p_hac": row.get("p_hac"),
        "single_beta3_p_cluster": row.get("p_cluster"),
        "adj_r2": row["adj_r2"],
    }
    try:
        out["joint_wald_p_hac"] = float(hac.wald_test(hyp, scalar=True).pvalue)
        out["joint_wald_p_cluster"] = float(cl.wald_test(hyp, scalar=True).pvalue)
        out["joint_hypothesis"] = hyp
    except Exception as e:
        out["joint_wald_error"] = str(e)
        out["param_names"] = names
    return out


def split_ceir_stats(df: pd.DataFrame, variant: str) -> dict:
    pre = df[df["Date"] < CHINA_BAN]
    post = df[df["Date"] >= CHINA_BAN]
    form = "ret_30d ~ log_ceir_w + trend + fg + vol30"
    pre_r = fit_model(pre, form, "log_ceir_w")
    post_r = fit_model(post, form, "log_ceir_w")
    pre_row = pre_r[0] if isinstance(pre_r, tuple) else pre_r
    post_row = post_r[0] if isinstance(post_r, tuple) else post_r
    return {
        "variant": variant,
        "pre_coef": pre_row.get("coef"),
        "pre_p_hac": pre_row.get("p_hac"),
        "pre_p_cluster": pre_row.get("p_cluster"),
        "pre_n": pre_row.get("n"),
        "post_coef": post_row.get("coef"),
        "post_p_hac": post_row.get("p_hac"),
        "post_p_cluster": post_row.get("p_cluster"),
        "post_n": post_row.get("n"),
    }


def build_ratio_panel(complete: pd.DataFrame, kind: str) -> pd.DataFrame:
    out = complete.copy()
    daily_kwh = out["Energy_TWh_Annual"].astype(float) * 1e9 / 365.0
    if kind == "mcap_over_cum_twh":
        cum = np.cumsum(daily_kwh)
        ratio = out["Market_Cap"].astype(float) / cum
    elif kind == "mcap_over_cum_days":
        cum = np.arange(1, len(out) + 1, dtype=float)
        ratio = out["Market_Cap"].astype(float) / cum
    elif kind == "legacy_ceir":
        ratio = out["CEIR"].astype(float)
    else:
        raise ValueError(kind)
    out = out.copy()
    out["CEIR"] = ratio
    out["log_CEIR"] = np.log(ratio)
    return out


def document_seed(complete: pd.DataFrame) -> dict:
    c = complete.sort_values("Date")
    first = c.iloc[0]
    row_2019 = c[c["Date"] == "2019-01-01"].iloc[0]
    c2018 = c[c["Date"] < "2019-01-01"]
    return {
        "complete_start": str(c["Date"].min().date()),
        "first_day_cumulative_equals_daily": bool(
            np.isclose(first["cumulative_cost"], first["daily_cost_usd"], rtol=1e-9)
        ),
        "pre_2018_seed": 0.0,
        "sum_daily_cost_2018": float(c2018["daily_cost_usd"].sum()),
        "cumulative_on_2019_01_01": float(row_2019["cumulative_cost"]),
        "daily_on_2019_01_01": float(row_2019["daily_cost_usd"]),
        "implied_stock_entering_2019_01_01_before_that_day": float(
            row_2019["cumulative_cost"] - row_2019["daily_cost_usd"]
        ),
        "electricity_price_used_in_2018": float(c2018["electricity_price"].mode().iloc[0]),
        "energy_source": "CBECI annualised TWh → daily kWh = TWh*1e9/365",
        "interpretation": (
            "The ~$3.30bn figure on analysis_ready 2019-01-01 is NOT an external mysterious seed. "
            "It is the cumsum of daily_cost_usd from complete panel start 2018-01-01 through 2019-01-01 "
            "under the panel electricity_price (near-constant 0.076234375). "
            "Pre-2018 mining cost is NOT included (complete starts 2018-01-01 with cum=daily)."
        ),
    }


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    complete = load_complete()
    seed = document_seed(complete)
    (RESULTS / "ceir_cumulative_seed_audit.json").write_text(json.dumps(seed, indent=2), encoding="utf-8")

    # --- incremental info by regime ---
    baseline = prepare(pd.read_csv(PANEL, parse_dates=["Date"]))
    inc_rows = []
    inc_rows += incremental_block(baseline[baseline["Date"] < CHINA_BAN].copy(), "pre_ban")
    inc_rows += incremental_block(baseline[baseline["Date"] >= CHINA_BAN].copy(), "post_ban")
    # pooled with interaction focus
    pooled_form_ceir = "ret_30d ~ log_ceir_w + post_ban + log_ceir_x_post + trend + fg + vol30"
    pooled_bench = (
        "ret_30d ~ log_price + ret_trail_30 + ret_trail_180 + vol30 + fg + price_to_trend + trend + post_ban"
    )
    pooled_both = (
        "ret_30d ~ log_ceir_w + post_ban + log_ceir_x_post + log_price + ret_trail_30 + ret_trail_180 "
        "+ vol30 + fg + price_to_trend + trend"
    )
    for name, form, focus in [
        ("ceir_with_interaction", pooled_form_ceir, "log_ceir_w"),
        ("benchmark_only", pooled_bench, "log_price"),
        ("benchmark_plus_ceir_interaction", pooled_both, "log_ceir_w"),
    ]:
        res = fit_model(baseline, form, focus)
        row, hac, cl, s = res if isinstance(res, tuple) else (res, None, None, None)
        row = {"regime": "pooled", "model": name, **row}
        if name == "benchmark_plus_ceir_interaction" and hac is not None:
            try:
                row["incremental_wald_p_hac"] = float(hac.wald_test("log_ceir_w = 0", scalar=True).pvalue)
                row["incremental_wald_p_cluster"] = float(cl.wald_test("log_ceir_w = 0", scalar=True).pvalue)
                row["interaction_coef"] = float(hac.params.get("log_ceir_x_post", np.nan))
                row["interaction_p_hac"] = float(hac.pvalues.get("log_ceir_x_post", np.nan))
            except Exception as e:
                row["incremental_wald_error"] = str(e)
        inc_rows.append(row)
    inc_df = pd.DataFrame(inc_rows)
    inc_path = RESULTS / "ceir_incremental_information_by_regime.csv"
    inc_df.to_csv(inc_path, index=False)

    # --- joint Wald ---
    joint = joint_break_wald(baseline)
    (RESULTS / "ceir_joint_break_wald.json").write_text(json.dumps(joint, indent=2), encoding="utf-8")

    # --- economically distinct constructions ---
    variants = []
    # legacy baseline
    variants.append(split_ceir_stats(baseline, "legacy_panel"))

    # relative country-price vectors + freeze-last
    for name, vec in [
        ("geo_cambridge_prices_freeze", PRICE_CAMBRIDGE),
        ("geo_datagath_prices_freeze", PRICE_DATAGATH),
        ("geo_fusion_prices_freeze", PRICE_FUSION),
    ]:
        p = geo_weighted_daily(complete, vec, post2022="freeze")
        rebuilt = rebuild_from_price(complete, p)
        ready = rebuilt[rebuilt["Date"] >= "2019-01-01"].copy()
        ready["fear_greed_index"] = complete.loc[complete["Date"] >= "2019-01-01", "fear_greed_index"].values
        ready["Returns"] = complete.loc[complete["Date"] >= "2019-01-01", "Returns"].values
        ready["in_analysis_period"] = 1
        variants.append(split_ceir_stats(prepare(ready), name))

    # post-2022 alternatives with cambridge prices
    for post_rule in ["us_dominant", "global_avg"]:
        p = geo_weighted_daily(complete, PRICE_CAMBRIDGE, post2022=post_rule)
        rebuilt = rebuild_from_price(complete, p)
        ready = rebuilt[rebuilt["Date"] >= "2019-01-01"].copy()
        ready["fear_greed_index"] = complete.loc[complete["Date"] >= "2019-01-01", "fear_greed_index"].values
        ready["Returns"] = complete.loc[complete["Date"] >= "2019-01-01", "Returns"].values
        ready["in_analysis_period"] = 1
        variants.append(split_ceir_stats(prepare(ready), f"geo_cambridge_{post_rule}"))

    # restricted observed geography
    raw = pd.read_csv(PANEL, parse_dates=["Date"])
    variants.append(split_ceir_stats(prepare(raw[raw["Date"] <= CAMBRIDGE_END].copy()), "restricted_to_cambridge_end"))

    # seed sensitivity on legacy prices
    for scale, label in [(0.5, "seed_2018_half"), (0.0, "seed_2018_zero"), (2.0, "seed_2018_double")]:
        rebuilt = rebuild_from_price(complete, complete["electricity_price"].astype(float), seed_scale=scale)
        ready = rebuilt[rebuilt["Date"] >= "2019-01-01"].copy()
        ready["fear_greed_index"] = complete.loc[complete["Date"] >= "2019-01-01", "fear_greed_index"].values
        ready["Returns"] = complete.loc[complete["Date"] >= "2019-01-01", "Returns"].values
        ready["in_analysis_period"] = 1
        variants.append(split_ceir_stats(prepare(ready), label))

    # benchmark ratios
    for kind in ["mcap_over_cum_twh", "mcap_over_cum_days"]:
        rebuilt = build_ratio_panel(complete, kind)
        ready = rebuilt[rebuilt["Date"] >= "2019-01-01"].copy()
        ready["fear_greed_index"] = complete.loc[complete["Date"] >= "2019-01-01", "fear_greed_index"].values
        ready["Returns"] = complete.loc[complete["Date"] >= "2019-01-01", "Returns"].values
        ready["in_analysis_period"] = 1
        variants.append(split_ceir_stats(prepare(ready), kind))

    var_df = pd.DataFrame(variants)
    var_path = RESULTS / "ceir_economic_constructions.csv"
    var_df.to_csv(var_path, index=False)

    # notes
    notes = f"""# CEIR Audit Pass 2 Notes

**Status:** Analytical only — do **not** treat as v11 authorization.

## Cumulative-cost “seed” (~$3.30bn on 2019-01-01)

See `empirical_results/ceir_cumulative_seed_audit.json`.

- Complete panel starts **2018-01-01** with `cumulative_cost = daily_cost` (no pre-2018 stock).
- Sum of 2018 daily costs ≈ **${seed['sum_daily_cost_2018']/1e9:.3f}bn**.
- On **2019-01-01**, cumulative ≈ **${seed['cumulative_on_2019_01_01']/1e9:.3f}bn** (= 2018 sum + that day’s cost).
- Analysis panel drops 2018 rows but **keeps** that cumulative stock in the denominator.
- Built under near-constant `electricity_price ≈ {seed['electricity_price_used_in_2018']}`.

## Incremental information (regime-specific)

See `ceir_incremental_information_by_regime.csv`.

Interpret pre-ban and post-ban blocks separately. Pooled-only horse races can average away the thesis claim.

## Joint break Wald

See `ceir_joint_break_wald.json`.

Language until joint evidence is clear and stable across constructions:

> specification-dependent or suggestive evidence of parameter instability

## Economic constructions

See `ceir_economic_constructions.csv` for alternative geography price vectors, post-2022 rules,
seed scales, and non-price ratios (MCap/cum TWh, MCap/cum days).

If non-price ratios behave like CEIR, electricity pricing is not adding identifiable information.
"""
    (PKG / "CEIR_AUDIT_PASS2_NOTES.md").write_text(notes, encoding="utf-8")

    print(json.dumps(seed, indent=2))
    print("--- incremental ---")
    print(inc_df.to_string(index=False))
    print("--- joint ---")
    print(json.dumps(joint, indent=2))
    print("--- constructions ---")
    print(var_df.to_string(index=False))
    print("ceir_audit_pass2_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
