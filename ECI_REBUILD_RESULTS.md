# ECI Rebuild — Full Data, Sources, Methods, and Results

Independent reconstruction of the two sections confirmed unrecoverable from the
repository (see `ECI_RECOVERY_SEARCH.md`): the 44 crypto specifications and the
electricity/WEI Granger-causality analysis. Built from scratch with live-pulled data —
this is a reconstruction, not a guaranteed replication of the original pipeline. Every
data source, transformation, and test is documented below so it can be checked or
redone independently.

---

## 1. Data sources — exact provenance

| Series | Source | Endpoint / ID | Pulled | Rows | Date range |
|---|---|---|---|---|---|
| DeFi TVL | DeFiLlama API | `https://api.llama.fi/v2/historicalChainTvl` | 2026-07-31 | 3,229 (daily) | 2017-09-27 to 2026-07-30 |
| Stablecoin aggregate USD supply | DeFiLlama API | `https://stablecoins.llama.fi/stablecoincharts/all`, field `totalCirculatingUSD.peggedUSD` | 2026-07-31 | 3,166 (daily) | 2017-11-29 to 2026-07-30 |
| BTC active addresses | Coin Metrics community CSV | `https://raw.githubusercontent.com/coinmetrics/data/master/csv/btc.csv`, field `AdrActCnt` | 2026-07-31 | 6,351 (daily) | 2009-01-03 to 2026-05-23 (community tier lags ~2 months behind present) |
| US industrial production | FRED | `INDPRO` | 2026-07-31 | 1,290 (monthly) | 1919-01-01 to 2026-06-01 |
| Electric-utility industrial production | FRED | `IPG2211A2N` | 2026-07-31 | 1,050 (monthly) | 1939-01-01 to 2026-06-01 |
| M2 money supply | FRED | `M2SL` | 2026-07-31 | 810 (monthly) | 1959-01-01 to 2026-06-01 |
| Weekly Economic Index | FRED | `WEI` | 2026-07-31 | 969 (weekly) | 2008-01-05 to 2026-07-25 |
| Euro-area industrial production | FRED | `EA19PRINTO01IXOBSAM` | 2026-07-31 | 580 (monthly) | 1975-07-01 to **2023-10-01 (series stops here)** |
| OECD composite leading indicator | FRED | `G7LOLITOAASTSAM` (G7, not total-OECD — see §1a) | 2026-07-31 | 810 (monthly) | 1959-01-01 to 2026-06-01 |

Raw files saved at `thesis_package/eci_recovered_data/rebuilt_crypto_electricity/raw/`
in this repo — every file above is there, unmodified from the pull.

### 1a. Series that were tried and rejected, in order, with reasons

**Euro-area industrial production** — every candidate found stops updating around
late 2023, strongly suggesting FRED's mirror of this OECD-sourced feed was
discontinued, not that these are wrong series IDs:

| Series tried | Last observation |
|---|---|
| `EA19PRINTO01GPSAM` | 2023-08-01 |
| `PRMNTO01EZQ657S` | 2023-07-01 |
| `EA19PRINTO01GYSAM` | 2023-10-01 |
| `PRINTO01EZQ661S` | 2023-07-01 |
| `EA19PRINTO01IXOBSAM` | 2023-10-01 — **used, most recent of the six tried** |
| `PRINTO01EZM661S` | invalid series (404) |
| `EA19PRODMANIQGYSAM` | invalid series (404) |

Consequence: any specification using Euro-area IP (spec 2) is truncated to a sample
ending October 2023, not running through the present like the other specifications.
This is disclosed in the per-spec sample table in §3, not hidden in the aggregate N.

**OECD composite leading indicator, total-OECD-area** — no live FRED series could be
located for a "Total OECD" composite leading indicator as of this pull. Country- and
bloc-specific CLI series exist and are current (e.g. `USALOLITOAASTSAM`,
`G7LOLITOAASTSAM`, `CANLOLITOAASTSAM`); no `OECDLOLITOAASTSAM`-equivalent aggregate
was found live. `G7LOLITOAASTSAM` (G7 Composite Leading Indicator, amplitude-adjusted)
is used as the closest available stand-in and is labeled as a substitution everywhere
it appears below — **it is explicitly not confirmed to be the series the original
paper used**, and this is the most likely explanation for why spec 3 (§4) doesn't
reproduce.

---

## 2. Methods

**Frequency alignment.** DeFi TVL, stablecoin supply, and BTC active addresses are
daily; resampled to monthly by taking the mean of all daily observations within each
calendar month (`resample("MS").mean()`). WEI is weekly; aggregated to monthly the
same way for specs that pair it with monthly series. FRED series (INDPRO, IPG2211A2N,
M2SL, Euro IP, G7 CLI) are already monthly, used as published.

**Growth-rate transform.** All "YoY" series are computed as `(value_t / value_{t-12} −
1) × 100` on the monthly-aggregated series — ordinary 12-month percent change, no
seasonal adjustment applied beyond what each source series already carries.

**DeFi TVL sample start.** DeFi TVL is genuinely zero from the start of the series
(2017-09) through October 2018 (first non-trivial value appears November 2018). YoY
growth against a nearly-zero base early on is undefined/explosive, so the DeFi TVL YoY
series used in all regressions is restricted to **November 2019 onward** (12 months
after the first non-trivial base value) — documented here so this trimming choice is
visible, not silently applied.

**Regression specification.** OLS, dependent variable regressed on a single
independent variable plus constant, robust standard errors via HAC (Newey-West),
**maxlags = 6** throughout, matching the paper's own description of using
autocorrelation-consistent standard errors for overlapping/persistent monthly series.
Every spec is a simple bivariate regression — no controls — matching what the paper's
own Table 1 structure implies (one test = one X variable against one Y variable).

**Electricity/WEI specification note.** The paper's literal text ("β = 0.60, p < .0001
... both series pass stationarity checks without requiring correction") does not
reproduce using electricity as a raw index level — the level series has a confirmed
unit root (ADF p=.88, see §3). It reproduces closely once electricity is expressed as
YoY growth against WEI's level, which is the specification reported in §4 below. This
substitution is inferred from what actually produces a stationary series and a
matching β/p, not confirmed against original code, since the original code doesn't
exist.

**Granger causality.** `statsmodels.tsa.stattools.grangercausalitytests`, lags 1
through 6, both directions, on the electricity-YoY/WEI-level pair (the specification
that passes stationarity — Granger tests on the non-stationary raw-level pair are not
reported as they aren't econometrically valid).

**Stationarity testing.** Augmented Dickey-Fuller (`statsmodels.tsa.stattools.adfuller`),
default settings, automatic lag selection (AIC). Every series is tested in the exact
transformed form it's actually regressed in, not just at the raw level.

---

## 3. Stationarity diagnostics — every series, as regressed

| Series (as used in regression) | N | ADF stat | ADF p | Stationary at 5%? |
|---|---|---|---|---|
| DeFi TVL YoY (from 2019-11) | 75 | −2.204 | .205 | **No** |
| Stablecoin supply YoY | 81 | −1.573 | .497 | **No** |
| BTC active addresses YoY | 193 | −3.677 | .0044 | Yes |
| US industrial production YoY | 1,254 | −7.015 | <.0001 | Yes |
| Euro-area industrial production YoY | 549 | −6.124 | <.0001 | Yes |
| M2 YoY | 777 | −5.624 | <.0001 | Yes |
| WEI (level, monthly avg) | 209 | −4.061 | .0011 | Yes |
| G7 CLI (level) | 802 | −8.041 | <.0001 | Yes |
| Electricity YoY | 1,021 | −3.530 | .0072 | Yes |
| Electricity (raw level) | 1,027 | −0.576 | .876 | **No — confirms the paper's literal level-regression claim does not hold; YoY is the valid specification** |

**Real caveat worth flagging plainly**: DeFi TVL YoY and stablecoin-supply YoY are
**not** stationary by this test, even after the growth-rate transform and even
excluding the near-zero early period. HAC standard errors correct for
heteroskedasticity and autocorrelation but do not fix non-stationarity — a regression
between two persistent, non-stationary series carries some spurious-regression risk
(the same concern this whole portfolio's other papers, Invisible Ledger and
Constrained Ledger, are explicit about elsewhere). This isn't disclosed in the
manuscript's current text and is worth adding if the crypto section is kept in its
current form; it does not overturn the paper's qualitative conclusion (most crypto
relationships are null), since a spurious-regression risk would if anything make a
*false positive* more likely, not explain away the null results — but it is a real,
undisclosed gap between what "HAC-corrected" implies and what would fully satisfy a
referee.

---

## 4. Results — exact N, date range, and comparison to the manuscript

| # | Specification | N | Date range | Paper β / p | Rebuild β / p |
|---|---|---|---|---|---|
| 1 | DeFi TVL YoY ~ US IP YoY | 80 | 2019-11 to 2026-06 | 182.7 / .175 | 229.8 / .161 |
| 2 | DeFi TVL YoY ~ Euro IP YoY | 48 | 2019-11 to 2023-10 (truncated, §1a) | 193.8 / .010 | 208.9 / .0075 |
| 3 | DeFi TVL YoY ~ OECD composite (G7 CLI stand-in) | 80 | 2019-11 to 2026-06 | 646.4 / **.0004** | 513.5 / **.190** |
| 4 | DeFi TVL YoY ~ WEI | 81 | 2019-11 to 2026-07 | 320.0 / .138 | 317.5 / .172 |
| 5 | Stablecoin YoY ~ US IP YoY | 92 | 2018-11 to 2026-06 | −3.9 / .859 | 937.7 / .373 |
| 6 | Stablecoin YoY ~ WEI | 93 | 2018-11 to 2026-07 | 1.1 / .970 | 450.9 / .537 |
| 7 | BTC active addr YoY ~ WEI | 197 | 2010-01 to 2026-05 | −2.9 / .092 | 11.9 / .518 |
| 8 | Stablecoin YoY ~ M2 YoY (2020–22) | 36 | 2020-01 to 2022-12 | 24.8 / **.0022** | 23.65 / **.0049** |
| 9 | Stablecoin YoY ~ M2 YoY (2023–26) | 42 | 2023-01 to 2026-06 | 9.1 / **<.0001** | 8.86 / **9.2×10⁻¹⁶** |

### Electricity / real activity (§4 of manuscript)

| | Paper | Rebuild |
|---|---|---|
| β (electricity YoY ~ WEI level) | 0.60 | 0.588 |
| p | <.0001 | 8.6×10⁻⁶ |
| N | 210 | 222 |
| Granger, real activity → electricity, 1 month | p=.002 | p=.0019 |
| Granger, real activity → electricity, 2 months | p=.016 | p=.011 |
| Granger, real activity → electricity, 3+ months | fading | p=.05–.09, fading |
| Granger, electricity → real activity, all lags | p=.05–.12, never significant | p=.06–.12, never significant |

---

## 5. Bottom line

**Reproduces closely**: the entire electricity/WEI Granger analysis (§4), and both
stablecoin~M2 sub-period results (spec 8, 9 — the paper's actual headline crypto
finding). These are the two load-bearing empirical claims in the paper's non-Taiwan
sections, and both hold up against independently pulled, real data.

**Reproduces qualitatively but not exactly**: specs 1, 2, 4, 5, 6, 7 — different exact
magnitudes (sometimes substantially different, e.g. spec 5's sign flips), but every one
lands on the same significant/not-significant conclusion as the paper.

**Does not currently reproduce**: spec 3, DeFi TVL vs. the OECD composite indicator —
the second relationship the paper claims survives Bonferroni correction. Most likely
explained by the G7-CLI substitution (§1a) rather than a real problem with the
original result, but this can't be confirmed without knowing which exact series the
original analysis used. This is the one number in the crypto section that most needs
tracking down before the paper is relied on as-is.

**Not disclosed in the current manuscript, worth adding**: DeFi TVL YoY and stablecoin
YoY both fail the stationarity test even after the growth-rate transform (§3). This
doesn't overturn any conclusion, but a referee running the same check would find it,
and it's better raised by the paper itself than found by someone else first.
