"""ECI stablecoin~M2 diagnostic and rebuild.
Original raw data pulled 2026-07-31 (see manifests/raw_sha256.txt for hashes).
No fresh pull performed; source vintage is the original July 31 snapshot.
"""
import json
import sys
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller, grangercausalitytests
from statsmodels.stats.diagnostic import acorr_ljungbox, het_breuschpagan
from statsmodels.stats.stattools import durbin_watson
from statsmodels.tsa.stattools import coint
from arch.unitroot import KPSS, PhillipsPerron
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf

RAW = "/home/phyrexian/Downloads/llm_automation/project_portfolio/Solarpunk-bitcoin/thesis_package/eci_reproduction/raw"
OUT = "/home/phyrexian/Downloads/llm_automation/project_portfolio/Solarpunk-bitcoin/thesis_package/eci_reproduction/outputs"
FIG = "/home/phyrexian/Downloads/llm_automation/project_portfolio/Solarpunk-bitcoin/thesis_package/eci_reproduction/figures"

# ============================================================
# 1. LOAD AND BUILD EXACT-WINDOW SERIES
# ============================================================

sc_raw = json.load(open(f"{RAW}/stablecoin_supply.json"))
sc_daily_mean = pd.Series({
    pd.to_datetime(int(r["date"]), unit="s"): r.get("totalCirculatingUSD", {}).get("peggedUSD")
    for r in sc_raw
}).sort_index().dropna()
sc_monthly_mean = sc_daily_mean.resample("MS").mean()
sc_monthly_last = sc_daily_mean.resample("MS").last()  # month-end proxy (daily series, last obs of month)

m2 = pd.read_csv(f"{RAW}/M2SL.csv", parse_dates=["observation_date"]).rename(
    columns={"observation_date": "date", "M2SL": "value"}).set_index("date")["value"]

def yoy(s):
    return (s / s.shift(12) - 1) * 100

sc_yoy_mean = yoy(sc_monthly_mean)
sc_yoy_last = yoy(sc_monthly_last)
m2_yoy = yoy(m2)

# Full common sample (for secondary comparison)
full = pd.concat([sc_yoy_mean.rename("stablecoin_yoy"), m2_yoy.rename("m2_yoy")], axis=1).dropna()

# Exact regression window: 2023-01-01 to 2026-06-01, inclusive
window = full[(full.index >= "2023-01-01") & (full.index <= "2026-06-01")].copy()
window_full = pd.concat([
    sc_monthly_mean.rename("stablecoin_supply_usd_monthly_mean"),
    sc_yoy_mean.rename("stablecoin_yoy"),
    m2.rename("m2_level"),
    m2_yoy.rename("m2_yoy"),
], axis=1)
window_full = window_full[(window_full.index >= "2023-01-01") & (window_full.index <= "2026-06-01")]
window_full.index.name = "date"
window_full.to_csv(f"{OUT}/eci_stablecoin_m2_2023_2026.csv")
print(f"[1] Exact-window dataset saved. N={len(window_full.dropna())}, range {window_full.index.min().date()} to {window_full.index.max().date()}")

# ============================================================
# 2. REPRODUCE ORIGINAL SPECIFICATION
# ============================================================

results_log = []

def run_ols(y, x, label, maxlags=6, note=""):
    df = pd.concat([y.rename("y"), x.rename("x")], axis=1).dropna()
    if len(df) < 5:
        print(f"{label}: insufficient N ({len(df)})")
        return None
    X = sm.add_constant(df["x"])
    model = sm.OLS(df["y"], X).fit(cov_type="HAC", cov_kwds={"maxlags": maxlags}) if maxlags > 0 else sm.OLS(df["y"], X).fit()
    ci = model.conf_int().loc["x"].tolist()
    row = dict(
        label=label, N=len(df), maxlags=maxlags, beta=model.params["x"], se=model.bse["x"],
        tstat=model.tvalues["x"], pvalue=model.pvalues["x"], ci_low=ci[0], ci_high=ci[1],
        r2=model.rsquared, adj_r2=model.rsquared_adj, note=note,
        date_start=str(df.index.min().date()), date_end=str(df.index.max().date()),
    )
    results_log.append(row)
    print(f"{label}: N={row['N']}, beta={row['beta']:.4f}, se={row['se']:.4f}, t={row['tstat']:.3f}, "
          f"p={row['pvalue']:.4g}, 95%CI=[{ci[0]:.3f},{ci[1]:.3f}], R2={row['r2']:.4f}, adjR2={row['adj_r2']:.4f}")
    return model

print("\n=== [2] ORIGINAL SPECIFICATION REPRODUCTION ===")
m_orig = run_ols(window["stablecoin_yoy"], window["m2_yoy"], "Original: stablecoin_yoy ~ m2_yoy (2023-01 to 2026-06)", maxlags=6)

# ============================================================
# 3 & 4. STATIONARITY TESTS: exact window + full sample
# ============================================================

print("\n=== [3/4] STATIONARITY DIAGNOSTICS ===")
stationarity_rows = []

def stationarity_battery(series, name, sample_label):
    s = series.dropna()
    adf_stat, adf_p, adf_lags, adf_nobs, adf_crit, _ = adfuller(s, autolag="AIC")
    kpss_res = KPSS(s.values)
    pp_res = PhillipsPerron(s.values)
    row = dict(
        series=name, sample=sample_label, N=len(s),
        adf_stat=adf_stat, adf_p=adf_p, adf_lags=adf_lags,
        adf_crit_1pct=adf_crit["1%"], adf_crit_5pct=adf_crit["5%"],
        kpss_stat=kpss_res.stat, kpss_p=kpss_res.pvalue, kpss_bandwidth=kpss_res.lags,
        pp_stat=pp_res.stat, pp_p=pp_res.pvalue, pp_bandwidth=pp_res.lags,
    )
    stationarity_rows.append(row)
    print(f"{name} [{sample_label}]: N={row['N']} | ADF stat={adf_stat:.3f} p={adf_p:.4f} (lags={adf_lags}) | "
          f"KPSS stat={kpss_res.stat:.3f} p={kpss_res.pvalue:.4f} | PP stat={pp_res.stat:.3f} p={pp_res.pvalue:.4f}")
    return row

stationarity_battery(window["stablecoin_yoy"], "stablecoin_yoy", "exact_window_2023-01_2026-06")
stationarity_battery(window["m2_yoy"], "m2_yoy", "exact_window_2023-01_2026-06")
stationarity_battery(full["stablecoin_yoy"], "stablecoin_yoy", "full_common_sample")
stationarity_battery(full["m2_yoy"], "m2_yoy", "full_common_sample")

pd.DataFrame(stationarity_rows).to_csv(f"{OUT}/eci_stablecoin_m2_stationarity.csv", index=False)

# ============================================================
# 5. RESIDUAL DIAGNOSTICS
# ============================================================

print("\n=== [5] RESIDUAL DIAGNOSTICS (original 2023-2026 regression) ===")
df_orig = pd.concat([window["stablecoin_yoy"], window["m2_yoy"]], axis=1).dropna()
X = sm.add_constant(df_orig["m2_yoy"])
ols_plain = sm.OLS(df_orig["stablecoin_yoy"], X).fit()
resid = ols_plain.resid

resid_adf = adfuller(resid, autolag="AIC")
resid_kpss = KPSS(resid.values)
resid_pp = PhillipsPerron(resid.values)
lb = acorr_ljungbox(resid, lags=[1, 3, 6, 12], return_df=True)
dw = durbin_watson(resid)
bp = het_breuschpagan(resid, X)

influence = ols_plain.get_influence()
leverage = influence.hat_matrix_diag
cooks_d = influence.cooks_distance[0]

resid_diag = pd.DataFrame({
    "date": df_orig.index,
    "residual": resid.values,
    "leverage": leverage,
    "cooks_distance": cooks_d,
})
resid_diag.to_csv(f"{OUT}/eci_stablecoin_m2_residual_diagnostics.csv", index=False)

print(f"Residual ADF: stat={resid_adf[0]:.3f}, p={resid_adf[1]:.4f}")
print(f"Residual KPSS: stat={resid_kpss.stat:.3f}, p={resid_kpss.pvalue:.4f}")
print(f"Residual PP: stat={resid_pp.stat:.3f}, p={resid_pp.pvalue:.4f}")
print(f"Ljung-Box: \n{lb}")
print(f"Durbin-Watson: {dw:.3f}")
print(f"Breusch-Pagan: LM stat={bp[0]:.3f}, p={bp[1]:.4f}")
print(f"Max Cook's distance: {cooks_d.max():.4f} (obs {df_orig.index[cooks_d.argmax()].date()})")

# residual plot
fig, axes = plt.subplots(2, 1, figsize=(9, 6))
axes[0].plot(df_orig.index, resid.values, marker="o")
axes[0].axhline(0, color="gray", linewidth=0.8)
axes[0].set_title("Residuals: stablecoin_yoy ~ m2_yoy (2023-01 to 2026-06)")
plot_acf(resid, ax=axes[1], lags=min(20, len(resid)//2 - 1))
plt.tight_layout()
plt.savefig(f"{FIG}/eci_stablecoin_m2_residuals.png", dpi=150)
plt.close()

fig, ax = plt.subplots(1, 2, figsize=(10, 4))
plot_acf(resid, ax=ax[0], lags=min(20, len(resid)//2 - 1))
plot_pacf(resid, ax=ax[1], lags=min(20, len(resid)//2 - 1))
plt.tight_layout()
plt.savefig(f"{FIG}/eci_stablecoin_m2_acf.png", dpi=150)
plt.close()

# series plot
fig, ax = plt.subplots(figsize=(9, 4.5))
ax.plot(window.index, window["stablecoin_yoy"], label="stablecoin YoY", marker="o")
ax.plot(window.index, window["m2_yoy"], label="M2 YoY", marker="s")
ax.legend(); ax.set_title("Stablecoin YoY vs M2 YoY, 2023-01 to 2026-06")
plt.tight_layout()
plt.savefig(f"{FIG}/eci_stablecoin_m2_series.png", dpi=150)
plt.close()

# ============================================================
# 6. ALTERNATIVE STATIONARY SPECIFICATIONS
# ============================================================

print("\n=== [6] ALTERNATIVE SPECIFICATIONS ===")
d_sc = window["stablecoin_yoy"].diff()
d_m2 = window["m2_yoy"].diff()

specA = run_ols(d_sc, window["m2_yoy"], "Spec A: d(stablecoin_yoy) ~ m2_yoy", maxlags=6)
specB = run_ols(d_sc, d_m2, "Spec B: d(stablecoin_yoy) ~ d(m2_yoy)", maxlags=6)

# Spec C: d(sc)_t ~ d(sc)_{t-1} + m2_yoy_t + m2_yoy_{t-1}
specC_df = pd.DataFrame({
    "y": d_sc,
    "y_lag1": d_sc.shift(1),
    "m2": window["m2_yoy"],
    "m2_lag1": window["m2_yoy"].shift(1),
}).dropna()
Xc = sm.add_constant(specC_df[["y_lag1", "m2", "m2_lag1"]])
modelC = sm.OLS(specC_df["y"], Xc).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
print(f"Spec C: N={len(specC_df)}\n{modelC.summary().tables[1]}")
results_log.append(dict(label="Spec C: d(sc)_t ~ d(sc)_t-1 + m2_t + m2_t-1 (m2_t coef)", N=len(specC_df),
                         maxlags=6, beta=modelC.params["m2"], se=modelC.bse["m2"], tstat=modelC.tvalues["m2"],
                         pvalue=modelC.pvalues["m2"], ci_low=modelC.conf_int().loc["m2"][0],
                         ci_high=modelC.conf_int().loc["m2"][1], r2=modelC.rsquared, adj_r2=modelC.rsquared_adj,
                         note="distributed lag", date_start=str(specC_df.index.min().date()), date_end=str(specC_df.index.max().date())))

# Spec D: compact distributed lag, m2_yoy_t + m2_yoy_{t-1} on level stablecoin_yoy (not differenced), N~42 budget
specD_df = pd.DataFrame({
    "y": window["stablecoin_yoy"],
    "m2": window["m2_yoy"],
    "m2_lag1": window["m2_yoy"].shift(1),
}).dropna()
Xd = sm.add_constant(specD_df[["m2", "m2_lag1"]])
modelD = sm.OLS(specD_df["y"], Xd).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
print(f"Spec D: N={len(specD_df)}\n{modelD.summary().tables[1]}")
results_log.append(dict(label="Spec D: stablecoin_yoy ~ m2_yoy_t + m2_yoy_t-1 (m2_t coef)", N=len(specD_df),
                         maxlags=6, beta=modelD.params["m2"], se=modelD.bse["m2"], tstat=modelD.tvalues["m2"],
                         pvalue=modelD.pvalues["m2"], ci_low=modelD.conf_int().loc["m2"][0],
                         ci_high=modelD.conf_int().loc["m2"][1], r2=modelD.rsquared, adj_r2=modelD.rsquared_adj,
                         note="level y, distributed lag x", date_start=str(specD_df.index.min().date()), date_end=str(specD_df.index.max().date())))

# stationarity of differenced series
stationarity_battery(d_sc, "d(stablecoin_yoy)", "exact_window_diff")

pd.DataFrame(results_log).to_csv(f"{OUT}/eci_stablecoin_m2_regressions.csv", index=False)

# alt specs figure
fig, ax = plt.subplots(figsize=(9, 4.5))
labels_plot = [r["label"].split(":")[0] for r in results_log]
betas_plot = [r["beta"] for r in results_log]
pvals_plot = [r["pvalue"] for r in results_log]
colors = ["#1a6fdb" if p < 0.05 else "#b0b0b0" for p in pvals_plot]
ax.barh(labels_plot, betas_plot, color=colors)
ax.set_xlabel("coefficient on M2 YoY (or its equivalent)")
ax.set_title("All specifications: coefficient on M2 YoY (blue = p<.05)")
plt.tight_layout()
plt.savefig(f"{FIG}/eci_stablecoin_m2_alternative_specs.png", dpi=150)
plt.close()

# ============================================================
# 7. LEVELS AND COINTEGRATION
# ============================================================

print("\n=== [7] LEVELS / COINTEGRATION ===")
log_sc = np.log(sc_monthly_mean)
log_m2 = np.log(m2)
lvl = pd.concat([log_sc.rename("log_sc"), log_m2.rename("log_m2")], axis=1).dropna()
lvl_window = lvl[(lvl.index >= "2023-01-01") & (lvl.index <= "2026-06-01")]

coint_rows = []
for name, s in [("log_stablecoin_supply", lvl_window["log_sc"]), ("log_m2", lvl_window["log_m2"])]:
    r = stationarity_battery(s, name, "exact_window_levels")
    coint_rows.append(r)

# integration order check: are both non-stationary at level, stationary after 1 diff?
d1_sc = lvl_window["log_sc"].diff().dropna()
d1_m2 = lvl_window["log_m2"].diff().dropna()
adf_d1_sc = adfuller(d1_sc, autolag="AIC")
adf_d1_m2 = adfuller(d1_m2, autolag="AIC")
print(f"First-differenced log_sc: ADF p={adf_d1_sc[1]:.4f}")
print(f"First-differenced log_m2: ADF p={adf_d1_m2[1]:.4f}")

level_adf_sc = adfuller(lvl_window["log_sc"], autolag="AIC")[1]
level_adf_m2 = adfuller(lvl_window["log_m2"], autolag="AIC")[1]
both_i1 = (level_adf_sc > 0.05) and (level_adf_m2 > 0.05) and (adf_d1_sc[1] < 0.05) and (adf_d1_m2[1] < 0.05)

coint_result = {"both_appear_I1": both_i1, "level_adf_p_log_sc": level_adf_sc, "level_adf_p_log_m2": level_adf_m2,
                "diff_adf_p_log_sc": adf_d1_sc[1], "diff_adf_p_log_m2": adf_d1_m2[1]}
print(f"Both series appear I(1)? {both_i1}")

if both_i1:
    coint_t, coint_p, coint_crit = coint(lvl_window["log_sc"], lvl_window["log_m2"])
    Xeg = sm.add_constant(lvl_window["log_m2"])
    eg_model = sm.OLS(lvl_window["log_sc"], Xeg).fit()
    coint_result.update({
        "engle_granger_run": True, "eg_coint_stat": coint_t, "eg_coint_p": coint_p,
        "eg_crit_1pct": coint_crit[0], "eg_crit_5pct": coint_crit[1], "eg_crit_10pct": coint_crit[2],
        "eg_beta": eg_model.params["log_m2"], "eg_beta_p": eg_model.pvalues["log_m2"],
    })
    print(f"Engle-Granger: stat={coint_t:.3f}, p={coint_p:.4f}, beta={eg_model.params['log_m2']:.4f}")
else:
    coint_result["engle_granger_run"] = False
    coint_result["reason"] = "Integration orders not confirmed both I(1) in exact window (small-sample ADF power is low at N~42); Engle-Granger not run to avoid a forced/unsupported cointegration claim."
    print("Engle-Granger NOT run:", coint_result["reason"])

pd.DataFrame([coint_result]).to_csv(f"{OUT}/eci_stablecoin_m2_cointegration.csv", index=False)

# ============================================================
# 8. SENSITIVITY ANALYSIS
# ============================================================

print("\n=== [8] SENSITIVITY ANALYSIS ===")
sensitivity_rows = []

endpoints = {
    "2023-01_to_2025-12": ("2023-01-01", "2025-12-01"),
    "2023-01_to_2026-03": ("2023-01-01", "2026-03-01"),
    "2023-01_to_2026-06": ("2023-01-01", "2026-06-01"),
}
maxlags_grid = [0, 3, 6, 12]
agg_variants = {"monthly_mean": sc_yoy_mean, "monthly_last": sc_yoy_last}

for agg_name, sc_series in agg_variants.items():
    for ep_name, (start, end) in endpoints.items():
        sub = pd.concat([sc_series.rename("y"), m2_yoy.rename("x")], axis=1).dropna()
        sub = sub[(sub.index >= start) & (sub.index <= end)]
        if len(sub) < 8:
            continue
        for ml in maxlags_grid:
            X = sm.add_constant(sub["x"])
            if ml == 0:
                model = sm.OLS(sub["y"], X).fit()
            else:
                model = sm.OLS(sub["y"], X).fit(cov_type="HAC", cov_kwds={"maxlags": ml})
            sensitivity_rows.append(dict(
                aggregation=agg_name, endpoint=ep_name, maxlags=ml, N=len(sub),
                beta=model.params["x"], pvalue=model.pvalues["x"],
            ))

sens_df = pd.DataFrame(sensitivity_rows)
sens_df.to_csv(f"{OUT}/eci_stablecoin_m2_sensitivity.csv", index=False)
print(sens_df.to_string())

print("\n=== DONE ===")
