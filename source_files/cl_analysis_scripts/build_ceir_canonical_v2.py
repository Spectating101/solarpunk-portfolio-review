#!/usr/bin/env python3
"""
Canonical CEIR panel generator (audit pass 2).

Writes a NEW reproducible panel; does NOT overwrite:
  thesis_package/empirical_results/bitcoin_ceir_analysis_ready.csv

Output:
  thesis_package/empirical_results/bitcoin_ceir_canonical_v2.csv
  thesis_package/empirical_results/bitcoin_ceir_canonical_v2_meta.json

Construction (explicit):
  - Energy: CBECI annualised TWh
  - Geography: Cambridge mining map Sep 2019–Jan 2022
  - Country prices: cambridge.py constants (documented)
  - Post-2022: freeze last weighted month
  - Pre-Sep-2019: first Cambridge month weights
  - Cumulative from 2018-01-01 (no pre-2018 seed)
  - CEIR = Market_Cap / cumulative_cost
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EMP = ROOT / "empirical"
OUT = ROOT / "thesis_package" / "empirical_results"

PRICE = {
    "china": 0.040,
    "usa": 0.065,
    "russia": 0.050,
    "kazakhstan": 0.045,
    "canada": 0.070,
    "malaysia": 0.055,
    "iran": 0.035,
    "others": 0.060,
}


def main() -> int:
    complete_legacy = pd.read_csv(OUT / "bitcoin_ceir_complete.csv", parse_dates=["Date"]).sort_values("Date")
    geo = pd.read_csv(EMP / "cambridge_mining_distribution.csv", parse_dates=["date"]).sort_values("date")
    countries = [c for c in geo.columns if c != "date"]

    def weighted(row) -> float:
        p = 0.0
        wsum = 0.0
        for c in countries:
            w = float(row[c])
            if w <= 0:
                continue
            key = c if c in PRICE else ("usa" if c == "us" else "others")
            p += w * PRICE.get(key, PRICE["others"])
            wsum += w
        if wsum < 0.99:
            p += (1.0 - wsum) * PRICE["others"]
        return p

    monthly = geo.copy()
    monthly["p"] = monthly.apply(weighted, axis=1)
    first_p = float(monthly["p"].iloc[0])
    last_p = float(monthly["p"].iloc[-1])
    first_d = monthly["date"].iloc[0]
    last_d = monthly["date"].iloc[-1]

    df = complete_legacy[["Date", "Price", "Returns", "Market_Cap", "Energy_TWh_Annual", "fear_greed_index"]].copy()
    # map monthly weights onto days
    price = []
    for d in df["Date"]:
        if d < first_d:
            price.append(first_p)
        elif d > last_d:
            price.append(last_p)
        else:
            # nearest month on or before d
            sub = monthly[monthly["date"] <= d]
            price.append(float(sub["p"].iloc[-1]) if len(sub) else first_p)
    df["electricity_price"] = price
    daily_kwh = df["Energy_TWh_Annual"].astype(float) * 1e9 / 365.0
    df["daily_cost_usd"] = daily_kwh * df["electricity_price"]
    df["cumulative_cost"] = df["daily_cost_usd"].cumsum()
    df["CEIR"] = df["Market_Cap"].astype(float) / df["cumulative_cost"]
    df["log_CEIR"] = np.log(df["CEIR"])
    df["post_china_ban"] = (df["Date"] >= "2021-06-20").astype(int)
    df["in_analysis_period"] = (df["Date"] >= "2019-01-01").astype(int)
    df["construction"] = "canonical_v2_cambridge_prices_freeze_last"

    out_path = OUT / "bitcoin_ceir_canonical_v2.csv"
    df.to_csv(out_path, index=False)
    meta = {
        "output": str(out_path.relative_to(ROOT)),
        "does_not_overwrite": "bitcoin_ceir_analysis_ready.csv",
        "country_prices": PRICE,
        "geography": "cambridge_mining_distribution.csv",
        "post_2022_rule": "freeze_last_weighted_month",
        "pre_cambridge_rule": "first_month_weights",
        "cumulative_start": "2018-01-01 from legacy complete calendar (same dates/energy/mcap)",
        "note": "Uses legacy complete panel's Price/Market_Cap/Energy/FG for comparability; only rebuilds p and CEIR.",
    }
    (OUT / "bitcoin_ceir_canonical_v2_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"wrote {out_path}")
    print(f"n={len(df)} price_unique≈{df.electricity_price.nunique()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
