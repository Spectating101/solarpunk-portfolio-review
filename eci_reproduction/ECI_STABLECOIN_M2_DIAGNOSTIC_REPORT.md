# ECI Stablecoin~M2 Diagnostic Report

## 1. Files and source vintage

Original raw pull was located, not missing: `thesis_package/eci_recovered_data/rebuilt_crypto_electricity/raw/` (untracked, dated 2026-07-31). Verified byte-identical to the pull and copied into a stable, dedicated directory without modifying the originals:

```
thesis_package/eci_reproduction/
  raw/           <- byte-identical copies of the 2026-07-31 pull
  processed/
  scripts/eci_stablecoin_m2_diagnostics.py
  outputs/       <- 6 CSVs (see §9 below)
  figures/       <- 4 PNGs
  manifests/raw_sha256.txt
```

SHA-256 hashes of every original raw file recorded in `manifests/raw_sha256.txt`. No fresh pull was needed — this is the same July 31 vintage as the original rebuild, not a new one.

**Source**: `https://stablecoins.llama.fi/stablecoincharts/all`, field `totalCirculatingUSD.peggedUSD`; FRED `M2SL`.

## 2. Original-regression reproduction

**Reproduces exactly.** β=8.8606, SE=1.1024, t=8.037, p=9.17×10⁻¹⁶, N=42, 95% CI=[6.700, 11.021], R²=.845. Matches the claimed β≈8.86, p≈9.2×10⁻¹⁶ to four significant figures. No data revision, alignment issue, or software discrepancy — this is a clean, direct reproduction of the original number.

## 3. Exact-window stationarity verdict

| Series | ADF p | KPSS p | PP p |
|---|---|---|---|
| stablecoin_yoy (N=42) | .0145 (stationary) | .0101 (**non**-stationary) | .588 (non-stationary) |
| m2_yoy (N=42) | .960 (non-stationary) | .0055 (non-stationary) | .912 (non-stationary) |

**Verdict: ambiguous for stablecoin_yoy (tests disagree — ADF says stationary, KPSS and PP both say not), and non-stationary for m2_yoy across all three tests.** This is a materially different picture from the broader-sample framing in the current manuscript (which describes stablecoin_yoy as non-stationary and M2 as stationary) — in the exact 42-month regression window, it's m2_yoy that fails stationarity most consistently, not stablecoin_yoy. Full-sample diagnostics are also reported in `outputs/eci_stablecoin_m2_stationarity.csv` for comparison and show a broadly similar ambiguous pattern (ADF and PP disagree there too).

## 4. Residual diagnostics verdict

**Real, substantive problem.** From the plain OLS fit (before HAC correction) on the original 2023–2026 window:

- Durbin-Watson = **0.207** — severe positive autocorrelation (2.0 is the no-autocorrelation benchmark)
- Ljung-Box: p < 10⁻⁶ at lags 1, 3, 6, and 12 — residual autocorrelation is not a borderline call
- Breusch-Pagan: p = .0028 — real heteroskedasticity
- Residual ADF p=.46, KPSS p=.33, PP p=.64 — residuals themselves don't clearly resolve as stationary either
- Max Cook's distance 0.29 at the final observation (2026-06) — no single point is dominating the fit

This pattern — a huge, "extremely significant" bivariate coefficient sitting on top of residuals with DW near 0.2 — is close to the textbook signature of two persistent, imperfectly-differenced series moving together for reasons other than the modeled relationship. HAC standard errors correct for this in large samples; at N=42 with this much residual structure, the correction should not be taken as fully resolving it.

## 5. Alternative-specification results

| Spec | Description | N | β (or M2 coef) | p | Verdict |
|---|---|---|---|---|---|
| Original | stablecoin_yoy ~ m2_yoy | 42 | 8.86 | 9.2×10⁻¹⁶ | Reproduces, but see residual diagnostics above |
| A | Δstablecoin_yoy ~ m2_yoy | 41 | **−0.33** | .273 | **Not significant, wrong sign** |
| B | Δstablecoin_yoy ~ Δm2_yoy | 41 | **3.71** | **.0015** | **Significant, correct sign, survives full differencing — at 42% of the original magnitude** |
| C | Δsc_t ~ Δsc_{t-1} + m2_t + m2_{t-1} | 40 | 2.40 (m2_t), −2.72 (m2_{t-1}) | .009 / .003 | Significant but with an offsetting negative lag — a genuinely dynamic, more complex pattern, not a clean confirmation |
| D | stablecoin_yoy ~ m2_yoy_t + m2_yoy_{t-1} | 41 | 6.23 | .191 | **Not significant once a lag term is added while keeping levels** |

**Verdict: the relationship does not uniformly survive reasonable respecification.** It fails in Spec A and Spec D, and only clearly survives in Spec B — the version that differences both sides, which is also the most defensible response to the mixed stationarity findings in §3. Spec B's result (β=3.71, p=.0015) is real evidence of a liquidity association, but it is a materially smaller and differently-shaped claim than "β≈8.86, survives Bonferroni, strongest repeatable crypto result."

## 6. Cointegration result

**Not run, correctly.** Both `log(stablecoin supply)` and `log(M2)` fail to reject a unit root at the level (ADF p=.87 and p=1.00 respectively, consistent with I(1)). But `log(stablecoin supply)`'s first difference does **not** clearly reject a unit root either (ADF p=.10, above the .05 threshold), while `log(M2)`'s first difference does (p=.0003). Since both series were not confirmed to be integrated of the same order, Engle-Granger was not run, per the predeclared rule against forcing a cointegration interpretation onto ambiguous evidence. This is a genuine ambiguity from small-sample ADF power at N=42, not a negative result — it means "cannot confirm," not "confirmed absent."

## 7. Sensitivity results

Full grid in `outputs/eci_stablecoin_m2_sensitivity.csv` (2 aggregation methods × 3 endpoints × 4 HAC maxlags = 24 rows, all reported, none cherry-picked). Two findings:

- The point estimate is stable across HAC maxlags choices for a fixed sample (as expected — maxlags only affects the reported SE, not β), ranging 8.69–10.43 depending on endpoint/aggregation.
- **The p-value is enormous (10⁻¹⁶ to 10⁻¹³⁸ range) across every single variant tested.** Given the residual diagnostics in §4, this is a warning sign, not a reassurance — p-values this extreme, this consistently, sitting on top of DW=0.2 residuals, are more consistent with a poorly-specified persistent-series regression than with a genuinely well-identified relationship of that strength.

## 8. Recommended manuscript treatment

This maps most closely to **Outcome D** from the predeclared decision rules, with an element of **Outcome A**: the evidence is small-sample-ambiguous on stationarity and cointegration, the original bivariate specification does not survive two of three reasonable respecifications, but a real, smaller, correctly-signed liquidity association does survive the specification that most directly addresses the stationarity concern (Spec B).

Concretely:
1. **Remove "strongest repeatable crypto result" from the manuscript.** The number that phrase was built on (β=8.86, p≈10⁻¹⁶) sits on residuals with DW=0.207 and does not survive being properly differenced without shrinking by more than half and losing robustness.
2. **Report Spec B instead of, or alongside, the original bivariate regression** as the more defensible claim: a real, positive, statistically significant liquidity association between stablecoin supply growth and M2 growth, smaller than the headline number, surviving a specification that resolves the stationarity ambiguity found in §3.
3. **State plainly that Bonferroni correction and stationarity are answering different questions** — the original result's Bonferroni survival says nothing about whether the regression itself is well-specified, and this diagnostic shows it likely isn't in its original form.
4. **Make the Taiwan section the unambiguous empirical center of the paper**, consistent with Outcome D — it has no analogous stationarity or residual-diagnostic problems and reproduced exactly against independently recovered source data (see `ECI_REBUILD_RESULTS.md`).
5. **Preserve the paper's main negative conclusion.** Nothing here changes it — if anything it strengthens it: the one crypto relationship that looked like it might be a stable, general-purpose signal turns out to be smaller and more fragile than first reported, reinforcing rather than undercutting "the tested crypto measures do not establish a stable general-purpose real-economy indicator."

## Software versions

Python 3.13, pandas 3.0.5, statsmodels 0.14.6, scipy 1.18.0, arch (latest available at pull time, installed 2026-07-31 for this diagnostic — KPSS and Phillips-Perron tests were not available in the original rebuild's environment and are new to this pass).
