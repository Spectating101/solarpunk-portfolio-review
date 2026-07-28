#!/usr/bin/env python3
"""
Reproducible CEIR regression for the grounded thesis.

Runs the preferred level and differenced specifications on
`bitcoin_ceir_analysis_ready.csv`, writes summary CSVs, trading-rule JSON,
and the regression appendix.

Preferred spec (level):
  ret_30d ~ winsorized log(CEIR) + linear trend + standardized fear/greed + 30d vol
  HAC(30) and month-clustered SEs; China-ban split (2021-06-20).

Note: the panel's legacy `Returns_forward` column was 1-day forward; this script
recomputes true 30-day forward returns from Price and optionally refreshes the panel.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import f as f_dist
from scipy.stats import mstats

PKG = Path(__file__).resolve().parent
RESULTS = PKG / "empirical_results"
PANEL = RESULTS / "bitcoin_ceir_analysis_ready.csv"
LEVEL_SUMMARY = RESULTS / "ceir_analysis_summary.csv"
DIFF_SUMMARY = RESULTS / "ceir_analysis_summary_diff.csv"
APPENDIX_MD = PKG / "CEIR_REGRESSION_APPENDIX.md"
TRADING_JSON = RESULTS / "ceir_trading_rule_summary.json"

CHINA_BAN = pd.Timestamp("2021-06-20")
LEVEL_FORMULA = "ret_30d ~ log_ceir_w + trend + fg + vol30"
DIFF_FORMULA = "ret_30d ~ dlog_w + trend + fg + vol30"


@dataclass
class PeriodResult:
    n: int
    beta: float
    p_hac: float
    p_cluster: float
    se_hac: float


@dataclass
class RegressionBundle:
    pre: PeriodResult
    post: PeriodResult
    chow_p: float
    diff_pre: PeriodResult
    diff_post: PeriodResult
    econ_impact_30d_pct: float


def load_panel(refresh_forward: bool = True) -> pd.DataFrame:
    df = pd.read_csv(PANEL, parse_dates=["Date"]).sort_values("Date").reset_index(drop=True)
    if "in_analysis_period" in df.columns:
        df = df[df["in_analysis_period"] == 1].copy()
    df["ret_30d"] = df["Price"].shift(-30) / df["Price"] - 1
    if refresh_forward:
        df["Returns_forward"] = df["ret_30d"]
    df["log_ceir_w"] = mstats.winsorize(df["log_CEIR"].astype(float), limits=[0.01, 0.01])
    df["trend"] = np.arange(len(df))
    fg = df["fear_greed_index"].astype(float)
    df["fg"] = (fg - fg.mean()) / fg.std()
    df["vol30"] = df["Returns"].rolling(30).std()
    df["month"] = df["Date"].dt.to_period("M").astype(str)
    dlog = df["log_CEIR"].astype(float).diff()
    lo, hi = dlog.quantile([0.01, 0.99])
    df["dlog_w"] = dlog.clip(lo, hi)
    return df


def _fit_period(sub: pd.DataFrame, formula: str, regressor: str) -> PeriodResult:
    cols = ["ret_30d", "month"] + [
        c for c in ["log_ceir_w", "dlog_w", "trend", "fg", "vol30"] if c in formula
    ]
    s = sub.dropna(subset=cols).copy()
    hac = smf.ols(formula, data=s).fit(cov_type="HAC", cov_kwds={"maxlags": 30})
    cl = smf.ols(formula, data=s).fit(cov_type="cluster", cov_kwds={"groups": s["month"]})
    return PeriodResult(
        n=len(s),
        beta=float(hac.params[regressor]),
        p_hac=float(hac.pvalues[regressor]),
        p_cluster=float(cl.pvalues[regressor]),
        se_hac=float(hac.bse[regressor]),
    )


def chow_pvalue(pre: pd.DataFrame, post: pd.DataFrame, formula: str) -> float:
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


def run_regressions(df: pd.DataFrame) -> RegressionBundle:
    pre = df[df["Date"] < CHINA_BAN]
    post = df[df["Date"] >= CHINA_BAN]
    pre_res = _fit_period(pre, LEVEL_FORMULA, "log_ceir_w")
    post_res = _fit_period(post, LEVEL_FORMULA, "log_ceir_w")
    diff_pre = _fit_period(pre, DIFF_FORMULA, "dlog_w")
    diff_post = _fit_period(post, DIFF_FORMULA, "dlog_w")
    chow = chow_pvalue(pre, post, LEVEL_FORMULA)
    s_pre = pre.dropna(subset=["ret_30d", "log_ceir_w", "trend", "fg", "vol30"])
    sd = float(s_pre["log_ceir_w"].std())
    econ = sd * pre_res.beta * 100
    return RegressionBundle(
        pre=pre_res,
        post=post_res,
        chow_p=chow,
        diff_pre=diff_pre,
        diff_post=diff_post,
        econ_impact_30d_pct=econ,
    )


def run_trading_rule(panel: pd.DataFrame) -> dict:
    df = panel.sort_values("Date").copy()
    ceir = df["CEIR"].astype(float)
    roll_mean = ceir.rolling(180, min_periods=60).mean()
    roll_std = ceir.rolling(180, min_periods=60).std()
    buy = ceir < (roll_mean - 1.5 * roll_std)
    strat = df["Returns"] * buy.shift(1)
    strat = strat.fillna(0.0)
    buyhold = df["Returns"].fillna(0.0)
    cum_s = (1.0 + strat).cumprod()
    cum_b = (1.0 + buyhold).cumprod()
    sharpe_s = float(strat.mean() / strat.std() * np.sqrt(365)) if strat.std() > 0 else 0.0
    sharpe_b = float(buyhold.mean() / buyhold.std() * np.sqrt(365)) if buyhold.std() > 0 else 0.0
    return {
        "panel": str(PANEL.relative_to(PKG.parent)),
        "signal": "buy when CEIR < rolling_mean_180d - 1.5 * rolling_std_180d",
        "total_return_strategy_pct": float((cum_s.iloc[-1] - 1.0) * 100),
        "total_return_buyhold_pct": float((cum_b.iloc[-1] - 1.0) * 100),
        "sharpe_strategy": sharpe_s,
        "sharpe_buyhold": sharpe_b,
        "buy_signals": int(buy.sum()),
        "note": (
            "Reproduced from bitcoin_ceir_analysis_ready.csv by ceir_regression.py. "
            "Strategy underperforms buy-and-hold on total return and Sharpe."
        ),
    }


def write_summaries(bundle: RegressionBundle) -> None:
    pd.DataFrame(
        [
            {
                "Pre_ban_N": bundle.pre.n,
                "Post_ban_N": bundle.post.n,
                "Pre_ban_CEIR_coef": bundle.pre.beta,
                "Post_ban_CEIR_coef": bundle.post.beta,
                "Chow_pvalue": bundle.chow_p,
                "Pre_ban_p_hac": bundle.pre.p_hac,
                "Post_ban_p_hac": bundle.post.p_hac,
                "Pre_ban_p_cluster": bundle.pre.p_cluster,
                "Post_ban_p_cluster": bundle.post.p_cluster,
                "Econ_impact_1sd_30d_pct": bundle.econ_impact_30d_pct,
            }
        ]
    ).to_csv(LEVEL_SUMMARY, index=False)

    pd.DataFrame(
        [
            {
                "Pre_ban_N": bundle.diff_pre.n,
                "Post_ban_N": bundle.diff_post.n,
                "Pre_ban_CEIR_coef": bundle.diff_pre.beta,
                "Post_ban_CEIR_coef": bundle.diff_post.beta,
                "Chow_pvalue": bundle.chow_p,
                "Pre_ban_p_hac": bundle.diff_pre.p_hac,
                "Post_ban_p_hac": bundle.diff_post.p_hac,
            }
        ]
    ).to_csv(DIFF_SUMMARY, index=False)


def write_appendix(bundle: RegressionBundle, trading: dict) -> None:
    text = f"""# CEIR Regression Appendix (auto-generated)

## Table A.1 — Preferred level specification

| Item | Value |
|------|------:|
| Pre-ban N | {bundle.pre.n} |
| Post-ban N | {bundle.post.n} |
| Pre-ban β (log CEIR) | {bundle.pre.beta:.4f} |
| Post-ban β (log CEIR) | {bundle.post.beta:.4f} |
| Pre-ban p (HAC) | {bundle.pre.p_hac:.4f} |
| Post-ban p (HAC) | {bundle.post.p_hac:.4f} |
| Pre-ban p (month cluster) | {bundle.pre.p_cluster:.4f} |
| Post-ban p (month cluster) | {bundle.post.p_cluster:.4f} |
| Chow p-value | {bundle.chow_p:.2e} |
| Econ. impact (1 SD log CEIR → 30d return) | {bundle.econ_impact_30d_pct:.1f}% |

**Specification:** `ret_30d = Price_{{t+30}}/Price_t - 1`; 1% winsorized `log(CEIR)`; controls: linear trend, standardized fear/greed, 30-day return volatility; HAC(30); month clustering; split at China ban ({CHINA_BAN.date()}).

## Table A.2 — Differenced CEIR (boundary condition)

| Item | Value |
|------|------:|
| Pre-ban β (Δlog CEIR) | {bundle.diff_pre.beta:.4f} (p={bundle.diff_pre.p_hac:.3f}) |
| Post-ban β (Δlog CEIR) | {bundle.diff_post.beta:.4f} (p={bundle.diff_post.p_hac:.3f}) |

CEIR effects are not robust to differencing — cite as a boundary condition.

## Table A.3 — Trading-rule negative result

| Metric | Value |
|--------|------:|
| Strategy total return (%) | {trading['total_return_strategy_pct']:.1f} |
| Buy-and-hold total return (%) | {trading['total_return_buyhold_pct']:.0f} |
| Sharpe (strategy) | {trading['sharpe_strategy']:.3f} |
| Sharpe (buy-and-hold) | {trading['sharpe_buyhold']:.3f} |

**Interpretation:** CEIR is explanatory evidence, not a viable trading strategy.

## Reproduce

```bash
python thesis_package/ceir_regression.py --refresh-panel
python thesis_package/generate_thesis_figures.py
npm run thesis:docx
```
"""
    APPENDIX_MD.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--refresh-panel",
        action="store_true",
        help="Write corrected 30-day Returns_forward back to the analysis panel CSV.",
    )
    args = parser.parse_args()

    raw = pd.read_csv(PANEL, parse_dates=["Date"])
    if args.refresh_panel:
        df_tmp = load_panel(refresh_forward=False)
        merged = raw.sort_values("Date").merge(df_tmp[["Date", "ret_30d"]], on="Date", how="left")
        merged["Returns_forward"] = merged["ret_30d"]
        merged.drop(columns=["ret_30d"], inplace=True)
        merged.to_csv(PANEL, index=False)
        empirical_panel = PKG.parent / "empirical" / "bitcoin_ceir_analysis_ready.csv"
        if empirical_panel.parent.exists():
            merged.to_csv(empirical_panel, index=False)

    df = load_panel(refresh_forward=False)

    bundle = run_regressions(df)
    trading = run_trading_rule(df)
    write_summaries(bundle)
    TRADING_JSON.write_text(json.dumps(trading, indent=2), encoding="utf-8")
    write_appendix(bundle, trading)

    print(f"wrote {LEVEL_SUMMARY.relative_to(PKG.parent)}")
    print(f"wrote {DIFF_SUMMARY.relative_to(PKG.parent)}")
    print(f"wrote {TRADING_JSON.relative_to(PKG.parent)}")
    print(f"wrote {APPENDIX_MD.relative_to(PKG.parent)}")
    print(
        f"pre beta={bundle.pre.beta:.4f} post beta={bundle.post.beta:.4f} "
        f"chow_p={bundle.chow_p:.2e}"
    )
    print("ceir_regression_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
