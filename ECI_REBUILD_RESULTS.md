# ECI Rebuild — Crypto Specifications & Electricity/WEI Granger Analysis

Rebuilt from scratch using live-pulled real data (DeFiLlama API, Coin Metrics community
CSV, FRED), since the original analysis was confirmed unrecoverable from this machine
(see `ECI_RECOVERY_SEARCH.md`). This is an independent reconstruction, not a guaranteed
byte-for-byte replication — data vintages, exact sample windows, and one substituted
series (noted below) differ from whatever the original pipeline used. Where results
diverge, that's reported plainly, not smoothed over.

## Data sources (all live-pulled, not simulated)

- DeFi TVL: `api.llama.fi/v2/historicalChainTvl` (daily, 2017–2026)
- Stablecoin aggregate USD supply: `stablecoins.llama.fi/stablecoincharts/all` (daily, 2017–2026)
- BTC active addresses: Coin Metrics community CSV, `AdrActCnt` field (daily, 2009–2026)
- US industrial production: FRED `INDPRO`
- Electric-utility industrial production: FRED `IPG2211A2N`
- M2 money supply: FRED `M2SL`
- Weekly Economic Index: FRED `WEI`
- Euro-area industrial production: FRED `EA19PRINTO01IXOBSAM` — **real data limitation**:
  every Euro-area IP series available on FRED stops updating around Oct 2023; this
  appears to be a genuine discontinuation of the OECD-sourced feed FRED mirrors, not a
  wrong series ID (tried 6 candidate series, all truncate at the same point).
- OECD composite leading indicator: FRED `G7LOLITOAASTSAM` (G7 CLI) — **substitution,
  not the original series**. No live "total OECD area" CLI series could be located on
  FRED; G7's is the closest available proxy and is used here explicitly labeled as such.

## Section 4 (electricity vs. real activity) — closely reproduced

The paper's literal claim (β=0.60, p<.0001, N=210, "both series pass stationarity
checks without requiring correction") only reproduces once electricity is used as a
**year-over-year growth rate**, not a raw index level — the raw level series has a unit
root (ADF p=.83) and gives a much weaker, insignificant relationship (β=0.39, p=.30).
Electricity YoY is stationary (ADF p=.001), matching the paper's stationarity claim.

| | Paper | My rebuild |
|---|---|---|
| β (electricity YoY ~ WEI) | 0.60 | 0.588 |
| p | <.0001 | 8.6×10⁻⁶ |
| N | 210 | 222 |
| Granger, real activity → electricity, 1mo | p=.002 | p=.0019 |
| Granger, real activity → electricity, 2mo | p=.016 | p=.011 |
| Granger, electricity → real activity, all lags | p=.05–.12, never significant | p=.06–.12, never significant |

This is a strong, independent confirmation. The direction, magnitude, and significance
pattern all reproduce closely from freshly pulled data using a different sample window
than whatever the original used.

## Core crypto specifications — mixed, reported honestly

| Test | Paper β / p | Rebuild β / p | Assessment |
|---|---|---|---|
| DeFi TVL YoY ~ US IP | 182.7 / .175 | 229.8 / .161 | Same sign, same order of magnitude, both non-significant. Close. |
| DeFi TVL YoY ~ Euro IP | 193.8 / .010 | 208.9 / .0075 | Close — both significant at ~.01, similar magnitude. |
| DeFi TVL YoY ~ OECD composite | 646.4 / **.0004** | 513.5 / **.190** | **Does not reproduce as significant.** Most likely explanation: G7 CLI substitution for the real "OECD composite" series — but this can't be confirmed without the original series. This is the one specification the paper claims survives Bonferroni besides M2; it deserves the most scrutiny before being relied on. |
| DeFi TVL YoY ~ WEI | 320.0 / .138 | 317.5 / .172 | Very close on both β and p. |
| Stablecoin YoY ~ US IP | −3.9 / .859 | 937.7 / .373 | Different sign and large magnitude gap, but both land on "not significant." |
| Stablecoin YoY ~ WEI | 1.1 / .970 | 450.9 / .537 | Same as above — different magnitude, same qualitative conclusion. |
| BTC active addr YoY ~ WEI | −2.9 / .092 | 11.9 / .518 | Different sign; paper's version is marginal (p=.092), mine isn't close to significant. |
| Stablecoin YoY ~ M2 (2020–22) | 24.8 / **.0022** | 23.65 / **.0049** | Close — both real and significant. This is the paper's actual headline crypto finding. |
| Stablecoin YoY ~ M2 (2023–26) | 9.1 / **<.0001** | 8.86 / **9.2×10⁻¹⁶** | Very close, both highly significant. |

## Bottom line

The paper's two load-bearing empirical claims — the electricity/WEI Granger result
(all of Section 4) and the stablecoin~M2 relationship in both sub-periods (the paper's
actual headline crypto finding, and the only crypto result besides OECD claimed to
survive Bonferroni) — **both reproduce closely from independently pulled, real data**.
That's a real, meaningful validation, not a coincidence of convenient rounding.

The specifications the paper reports as null (DeFi TVL vs. US IP, stablecoin/BTC vs.
US IP and WEI) also reproduce as null here, even where the exact magnitudes differ —
so the paper's qualitative conclusions on those hold up too.

**The one claim that does not currently reproduce is the DeFi TVL ~ OECD composite
indicator result** — the paper's second Bonferroni-surviving relationship. Given the
substituted series (G7 CLI standing in for an OECD-total series that doesn't appear to
exist as a current FRED feed), this is inconclusive rather than a confirmed error — but
it's the one specific number in the whole crypto section that a referee checking this
paper against fresh data would most likely flag, and it's worth tracking down the
original "OECD composite indicator" series identity before relying on it.
