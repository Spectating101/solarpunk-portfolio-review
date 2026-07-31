import json
import pandas as pd
import numpy as np
from statsmodels.tsa.stattools import adfuller

RAW = "/tmp/eci_rebuild/raw"

def load_fred(series):
    df = pd.read_csv(f"{RAW}/{series}.csv", parse_dates=["observation_date"])
    df = df.rename(columns={"observation_date": "date", series: "value"})
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.set_index("date")["value"]

us_ip = load_fred("INDPRO")
m2 = load_fred("M2SL")
wei = load_fred("WEI")
electricity = load_fred("IPG2211A2N")
eu_ip = load_fred("EA19PRINTO01IXOBSAM")
oecd_cli = load_fred("G7LOLITOAASTSAM")

tvl_raw = json.load(open(f"{RAW}/defi_tvl.json"))
tvl = pd.Series({pd.to_datetime(r["date"], unit="s"): r["tvl"] for r in tvl_raw}).sort_index()
tvl_m = tvl.resample("MS").mean()

sc_raw = json.load(open(f"{RAW}/stablecoin_supply.json"))
sc = pd.Series({pd.to_datetime(int(r["date"]), unit="s"): r.get("totalCirculatingUSD", {}).get("peggedUSD") for r in sc_raw}).sort_index()
sc = sc.dropna()
sc_m = sc.resample("MS").mean()

btc = pd.read_csv(f"{RAW}/btc_coinmetrics.csv", parse_dates=["time"])
btc_addr_m = btc.set_index("time")["AdrActCnt"].dropna().resample("MS").mean()

wei_m = wei.resample("MS").mean()

def yoy(s):
    return (s / s.shift(12) - 1) * 100

defi_yoy = yoy(tvl_m)[yoy(tvl_m).index >= "2019-11-01"]
sc_yoy = yoy(sc_m)
btc_yoy = yoy(btc_addr_m)
us_ip_yoy = yoy(us_ip)
eu_ip_yoy = yoy(eu_ip)
m2_yoy = yoy(m2)
elec_yoy = yoy(electricity)

print("=== ADF stationarity, every series used, in the form actually regressed ===\n")
series_to_test = {
    "DeFi TVL YoY (2019-11 on)": defi_yoy,
    "Stablecoin supply YoY": sc_yoy,
    "BTC active addresses YoY": btc_yoy,
    "US industrial production YoY": us_ip_yoy,
    "Euro-area industrial production YoY": eu_ip_yoy,
    "M2 YoY": m2_yoy,
    "WEI (level, monthly avg)": wei_m,
    "G7 CLI (level)": oecd_cli,
    "Electricity YoY": elec_yoy,
    "Electricity (level)": electricity,
}
for name, s in series_to_test.items():
    s2 = s.dropna()
    stat, p, lags, nobs, *_ = adfuller(s2)
    print(f"{name}: N={nobs}, ADF stat={stat:.3f}, p={p:.4f}, lags used={lags}")

print("\n=== Exact N and date range per specification ===\n")
def overlap(a, b, label):
    df = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    print(f"{label}: N={len(df)}, {df.index.min().date()} to {df.index.max().date()}")

overlap(defi_yoy, us_ip_yoy, "1. DeFi TVL YoY ~ US IP YoY")
overlap(defi_yoy, eu_ip_yoy, "2. DeFi TVL YoY ~ Euro IP YoY")
overlap(defi_yoy, oecd_cli, "3. DeFi TVL YoY ~ G7 CLI")
overlap(defi_yoy, wei_m, "4. DeFi TVL YoY ~ WEI")
overlap(sc_yoy, us_ip_yoy, "5. Stablecoin YoY ~ US IP YoY")
overlap(sc_yoy, wei_m, "6. Stablecoin YoY ~ WEI")
overlap(btc_yoy, wei_m, "7. BTC addr YoY ~ WEI")
sc_2022 = sc_yoy[(sc_yoy.index >= "2020-01-01") & (sc_yoy.index <= "2022-12-31")]
m2_2022 = m2_yoy[(m2_yoy.index >= "2020-01-01") & (m2_yoy.index <= "2022-12-31")]
overlap(sc_2022, m2_2022, "8. Stablecoin YoY ~ M2 YoY (2020-22)")
sc_2026 = sc_yoy[(sc_yoy.index >= "2023-01-01")]
m2_2026 = m2_yoy[(m2_yoy.index >= "2023-01-01")]
overlap(sc_2026, m2_2026, "9. Stablecoin YoY ~ M2 YoY (2023-26)")
