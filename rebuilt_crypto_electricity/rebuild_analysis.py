import json
import pandas as pd
import numpy as np
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller, grangercausalitytests

RAW = "/tmp/eci_rebuild/raw"

def load_fred(series):
    df = pd.read_csv(f"{RAW}/{series}.csv", parse_dates=["observation_date"])
    df = df.rename(columns={"observation_date": "date", series: "value"})
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.set_index("date")["value"]

# ---- FRED series ----
us_ip = load_fred("INDPRO")
m2 = load_fred("M2SL")
wei = load_fred("WEI")  # weekly
electricity = load_fred("IPG2211A2N")
eu_ip = load_fred("EA19PRINTO01IXOBSAM")  # truncated Oct 2023 - real data limitation
oecd_cli = load_fred("G7LOLITOAASTSAM")   # G7 CLI used as OECD-composite proxy - real substitution, disclosed

# ---- DeFi TVL (daily -> monthly mean) ----
tvl_raw = json.load(open(f"{RAW}/defi_tvl.json"))
tvl = pd.Series({pd.to_datetime(r["date"], unit="s"): r["tvl"] for r in tvl_raw}).sort_index()
tvl_m = tvl.resample("MS").mean()

# ---- Stablecoin aggregate USD supply (daily -> monthly mean) ----
sc_raw = json.load(open(f"{RAW}/stablecoin_supply.json"))
sc = pd.Series({pd.to_datetime(int(r["date"]), unit="s"): r.get("totalCirculatingUSD", {}).get("peggedUSD") for r in sc_raw}).sort_index()
sc = sc.dropna()
sc_m = sc.resample("MS").mean()

# ---- BTC active addresses (daily -> monthly mean) ----
btc = pd.read_csv(f"{RAW}/btc_coinmetrics.csv", parse_dates=["time"])
btc_addr = btc.set_index("time")["AdrActCnt"].dropna()
btc_addr_m = btc_addr.resample("MS").mean()

# ---- WEI monthly aggregation ----
wei_m = wei.resample("MS").mean()

def yoy(s):
    return (s / s.shift(12) - 1) * 100

def hac_reg(y, x, label, maxlags=6):
    df = pd.concat([y.rename("y"), x.rename("x")], axis=1).dropna()
    if len(df) < 10:
        print(f"{label}: insufficient overlap (n={len(df)})")
        return
    X = sm.add_constant(df["x"])
    model = sm.OLS(df["y"], X).fit(cov_type="HAC", cov_kwds={"maxlags": maxlags})
    beta = model.params["x"]
    p = model.pvalues["x"]
    print(f"{label}: n={len(df)}, beta={beta:.4f}, HAC p={p:.4g}")
    return beta, p, len(df)

print("=== CORE 9 SPECIFICATIONS (rebuilt from live-pulled data) ===\n")

defi_yoy = yoy(tvl_m)
defi_yoy = defi_yoy[defi_yoy.index >= "2019-11-01"]  # exclude near-zero-denominator period (TVL ~0 through Oct 2018)
sc_yoy = yoy(sc_m)
btc_yoy = yoy(btc_addr_m)
us_ip_yoy = yoy(us_ip)
eu_ip_yoy = yoy(eu_ip)
m2_yoy = yoy(m2)

hac_reg(defi_yoy, us_ip_yoy, "1. DeFi TVL YoY ~ US industrial production YoY")
hac_reg(defi_yoy, eu_ip_yoy, "2. DeFi TVL YoY ~ Euro-area industrial production YoY (TRUNCATED SAMPLE, see notes)")
hac_reg(defi_yoy, oecd_cli, "3. DeFi TVL YoY ~ G7 composite leading indicator (level, OECD-composite proxy)")
hac_reg(defi_yoy, wei_m, "4. DeFi TVL YoY ~ Weekly Economic Index (monthly avg)")
hac_reg(sc_yoy, us_ip_yoy, "5. Stablecoin YoY ~ US industrial production YoY")
hac_reg(sc_yoy, wei_m, "6. Stablecoin YoY ~ Weekly Economic Index")
hac_reg(btc_yoy, wei_m, "7. BTC active addresses YoY ~ Weekly Economic Index")

sc_2022 = sc_yoy[(sc_yoy.index >= "2020-01-01") & (sc_yoy.index <= "2022-12-31")]
m2_2022 = m2_yoy[(m2_yoy.index >= "2020-01-01") & (m2_yoy.index <= "2022-12-31")]
hac_reg(sc_2022, m2_2022, "8. Stablecoin YoY ~ M2 growth (2020-2022)")

sc_2026 = sc_yoy[(sc_yoy.index >= "2023-01-01")]
m2_2026 = m2_yoy[(m2_yoy.index >= "2023-01-01")]
hac_reg(sc_2026, m2_2026, "9. Stablecoin YoY ~ M2 growth (2023-2026)")

print("\n=== SECTION 4: Electricity vs WEI (LEVELS, as literally described) ===\n")
elec_m = electricity  # already monthly
common = pd.concat([elec_m.rename("elec"), wei_m.rename("wei")], axis=1).dropna()
common = common[(common.index >= "2009-01-01")]
print(f"N = {len(common)}, range {common.index.min()} to {common.index.max()}")

X = sm.add_constant(common["wei"])
model = sm.OLS(common["elec"], X).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
print(f"electricity (level) ~ WEI (level): beta={model.params['wei']:.4f}, p={model.pvalues['wei']:.4g}")

print("\n--- stationarity (ADF), LEVELS ---")
for name, s in [("electricity", common["elec"]), ("WEI", common["wei"])]:
    stat, p, *_ = adfuller(s.dropna())
    print(f"{name}: ADF stat={stat:.3f}, p={p:.4f}")

print("\n=== SECTION 4b: Electricity vs WEI (YoY growth, alternative specification) ===\n")
elec_yoy = yoy(elec_m)
common_yoy = pd.concat([elec_yoy.rename("elec"), wei_m.rename("wei")], axis=1).dropna()
X2 = sm.add_constant(common_yoy["wei"])
model2 = sm.OLS(common_yoy["elec"], X2).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
print(f"N = {len(common_yoy)}")
print(f"electricity YoY ~ WEI (level): beta={model2.params['wei']:.4f}, p={model2.pvalues['wei']:.4g}")

print("\n--- stationarity (ADF), electricity YoY ---")
stat, p, *_ = adfuller(common_yoy["elec"].dropna())
print(f"electricity YoY: ADF stat={stat:.3f}, p={p:.4f}")

print("\n--- Granger causality (YoY electricity, stationary), electricity -> WEI ---")
try:
    r1 = grangercausalitytests(common_yoy[["wei", "elec"]], maxlag=6, verbose=False)
    for lag, res in r1.items():
        print(f"lag {lag}: p={res[0]['ssr_ftest'][1]:.4f}")
except Exception as e:
    print("error:", e)

print("\n--- Granger causality (YoY electricity, stationary), WEI -> electricity ---")
try:
    r2 = grangercausalitytests(common_yoy[["elec", "wei"]], maxlag=6, verbose=False)
    for lag, res in r2.items():
        print(f"lag {lag}: p={res[0]['ssr_ftest'][1]:.4f}")
except Exception as e:
    print("error:", e)
