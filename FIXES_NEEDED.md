# Fix Brief — Confirmed Issues Across the Portfolio

Every item below marked CONFIRMED was independently re-derived (math recomputed from
source code, text re-checked against the actual document, or literature claim verified
via live search with citable sources) — not accepted on the strength of a review alone.
Items marked NOT CONFIRMED / RETRACTED are claims from an external review pass that did
not hold up under direct verification and should not be acted on.

---

## THE CONSTRAINED LEDGER (journal + full thesis versions)

### 1. CONFIRMED — Binomial option price is wrong in the paper text
- **Where**: `THE_CONSTRAINED_LEDGER_JOURNAL_VERSION` Table 2 and the full-thesis
  equivalent. Also hardcoded in `/tmp/build_cl_journal.py` line 176 and
  `/tmp/build_cl_complete.py` line 282: `"$0.0356/kWh"`.
- **Root cause**: this value is NOT computed live from `thesis_package/options_pricing.py`
  at build time — it's a stale hardcoded string. The actual `binomial_call()` function's
  own docstring already states the correct answer: *"Convergence verified at N=400:
  price stabilises at $0.01917/kWh."* Running the function directly against the source
  code's true Taiwan parameters (S0=K=$0.0525, σ=1.89, r=0.025, T=0.25) reproduces this:
  **binomial = $0.019173, Black-Scholes = $0.019185, Monte Carlo ≈ $0.0196 (2.08%
  divergence, matching the docstring's own note)**.
- **Fix**: replace `$0.0356/kWh` with `$0.0192/kWh` (or the precise `$0.01917/kWh`)
  everywhere it appears in both build scripts, and correct the derived "Monte Carlo
  price" and "Agreement between methods" cells to match (should already read ~2%,
  which is actually correct as-is — only the binomial/MC absolute values are wrong).

### 2. CONFIRMED — Spot/strike price stated in the paper doesn't match source code
- Paper states spot = **$0.0516/kWh**. `options_pricing.py` LOCATIONS["Taiwan"]["S0"]
  = **$0.0525**. Reconcile which is current and use it consistently; if $0.0525 is
  correct, the corrected binomial price above already uses it.

### 3. CONFIRMED — No conflict-of-interest disclosure exists in the document
- Grepped the full text of `THE_CONSTRAINED_LEDGER_JOURNAL_VERSION.docx` for
  "conflict," "disclos," "SPK," "SolarPunk," "author" — the only SPK/SolarPunk
  mention is a data-source citation in the Data and Code Statement, not a statement
  of the author's connection to the SolarPunk/SPK project being evaluated.
- **Fix**: add an explicit sentence, e.g. in the Data and Code Statement: "The author
  is affiliated with the SolarPunk project whose implementation is evaluated in
  Section 5." Non-negotiable before any submission.

### 4. CONFIRMED — Hayes (2019) misattribution
- Hayes's actual model (verified via [Applied Economics Letters](https://www.tandfonline.com/doi/abs/10.1080/13504851.2018.1488040)
  and [arXiv](https://arxiv.org/abs/1805.07610)) is a **marginal**-cost-of-production
  fundamental-value model — "the equipment and electricity costs of miners in relation
  to their expected block reward." CEIR (market cap ÷ **cumulative** mining expenditure)
  is a different construction than what Hayes proposed.
- **Fix**: either locate a source that actually defends the cumulative-cost ratio, or
  reframe as "a ratio circulating in practitioner/crypto analysis" and remove the direct
  Hayes citation from the specific claim being tested — cite Hayes only where the paper
  discusses the marginal-cost literature generally (which is legitimate).

### 5. CONFIRMED — Related prior finding not engaged with
- Marthinsen & Gordon (2022), *Quarterly Review of Economics and Finance* 85: 280–288
  (verified via [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1062976922000473)
  and [arXiv preprint](https://arxiv.org/abs/2204.13102)) already establish that
  "movements in bitcoin's mining cost follow, and therefore cannot cause, changes in
  bitcoin's price." This is closely related to CL's Section 3 negative result and is
  not currently cited or engaged with.
- **Fix**: add this citation to Section 2.2/3 and explicitly position CL's contribution
  relative to it — what CL adds (the four-part falsifiable standard, testing a specific
  cumulative-ratio construction) versus what's already established.

### 6. NOT CONFIRMED / RETRACTED — Margin requirement is NOT a math error
- External review claimed the $0.63/kWh margin was "off by ~30x." Running the paper's
  own defined formula directly from source (`VaR99 = S×[exp(Z99·σ·√T) − 1]`, then
  ×1.5 per `MARGIN_MULT`) reproduces **$0.6333/kWh** almost exactly. The arithmetic is
  correct. Do not "fix" this number.
- **Open question, not a bug**: a margin ~12× the underlying spot price is unusual and
  arguably worth a sentence of interpretive caveat (is this margin size actually
  practical?), but that is a design-discussion addition, not a correction.

### 7. WORTH RE-EXAMINING, NOT INDEPENDENTLY CONFIRMED — Test 1 (substitution) may be
   partly tautological
- The paper discloses that the intended geography-weighted electricity-price merge
  failed, leaving "a near-constant price path" for the legacy cost denominator. If the
  cumulative-cost series is effectively (constant price × cumulative electricity use),
  the .999989 correlation between the cost-ratio and the usage-ratio could be partly
  arithmetic rather than a finding. This needs the actual underlying cost-construction
  code checked (not included in this package) before concluding either way — flagging
  as open, not resolved.

### 8. STRUCTURAL / INTERPRETIVE (not a "wrong number," but the most consequential item)
- Section 5's claim that the built system passes "the same four-part standard" that
  eliminated CEIR is a category shift the paper doesn't name: Section 3's tests are
  statistical falsification tests on an empirical claim (placebo substitution, unit-root/
  differencing, a formal break test). Section 5's are functional tests on software the
  author wrote (three cities → three outputs; a testnet transaction). Recommend either
  renaming Section 5's framing to avoid claiming statistical-test equivalence, or adding
  an explicit paragraph distinguishing "falsification test" from "functional test" so
  the parallel reads as intentional rather than conflated.

---

## THE INVISIBLE LEDGER (NTA-accepted paper)

### 9. CONFIRMED — Reported ratios don't match the paper's own stated formula
- Paper defines: Ecosystem Ratio = (GTV − Revenue) / Revenue.
- Recomputing from the paper's own Table 1 figures:
  - Grab: (5.4−0.6)/0.6 = **8.00**, reported as 8.9
  - GoTo: (39.8−1.0)/1.0 = **38.80**, reported as 41.0
  - Shopee: (25.8−2.6)/2.6 = **8.92**, reported as 9.9
  - Total: (71.0−4.2)/4.2 = **15.90**, reported as 17.0
- GTV/Revenue (a different ratio) matches the reported figures far more closely
  (9.00, 39.80, 9.92, 16.90) — suggesting the table was actually computed as
  GTV/Revenue throughout, not the stated (GTV−Revenue)/Revenue.
- **Fix**: reconcile the formula and the reported numbers — either correct the stated
  definition to GTV/Revenue, or recompute every reported ratio (Tables 1, 2, 6, the
  abstract's "$17 flows..." line, and Figure 2) to match the stated (GTV−Revenue)/Revenue
  formula. This changes the headline ratio from 17.0× to ~15.9×, which does not change
  the qualitative finding but does change every number on the page.

### 10. NOT INDEPENDENTLY RE-DERIVED — DiD standard errors from interpolated data
- The reconstructed quarterly panel is built by linear interpolation between annual
  totals. Interpolation mechanically smooths a series, which can produce artificially
  small residuals and overstated significance. This is a legitimate methodological
  concern raised by the review; I did not have the raw annual data loaded to
  independently re-run the DiD and confirm the exact effect size. Flagging as
  a real risk worth a sensitivity check, not a confirmed numerical error.

---

## ENERGY CIRCULATION AS AN ECONOMIC INDICATOR (ECI)

### 11. CONFIRMED — Abstract contradicts the paper's own Table 2
- Abstract states: "β = 24.8–29.3, p < .0001 in both sub-periods."
- Table 2 reports: Stablecoin~M2 (2020–22): β=24.8, **p=.0022**; (2023–26): β=9.1, p<.0001.
- Neither the 29.3 figure nor "p<.0001 in both" appears anywhere in Table 2.
- **Fix**: correct the abstract to match Table 2 exactly: "β = 9.1–24.8 across
  sub-periods (p = .0022 and p < .0001 respectively)."

### 12. CONFIRMED — A result is marked as surviving Bonferroni correction when it doesn't
- Correction threshold: α = .05/44 = **.001136**.
- Stablecoin~M2 (2020–22): p = .0022 — this is *larger* than .001136, so it fails the
  correction, but the table marks it "yes" (survives).
- **Fix**: correct the "Survives Bonferroni" column for this row to "no," and update
  any prose that relies on both sub-periods surviving (Section 3.2/3.3, and the
  abstract fix above already addresses part of this).

### 13. CONFIRMED — WEI component overlaps with the regressor in Section 4
- Verified via [Dallas Fed](https://www.dallasfed.org/research/wei/about): the Weekly
  Economic Index's 10 components explicitly include "Electric utility output" sourced
  from the Edison Electric Institute.
- Section 4 regresses the Weekly Economic Index against U.S. electric-utility industrial
  production — one of the two variables is partly a component of the other, which is
  a mechanical/circularity risk for the reported β=0.60, p<.0001 relationship and for
  the Granger-causality claim built on it.
- **Fix**: either swap WEI for a real-activity index that provably excludes electricity
  (e.g., raw industrial production ex-utilities), or add an explicit limitations
  paragraph naming and quantifying the overlap, and soften the "resolved for the first
  time in this form" framing in the Contributions section accordingly.

### 14. Minor / lower priority
- Momentum Works citation year inconsistent (2023 in-text in some places vs. 2024 in
  references — not independently re-checked against IL's citation, which is a shared
  source; verify against the actual Momentum Works publication date).
- "283.09811 units" in CL (not ECI) reads as false precision for a policy-relevant
  figure; round for presentation.

---

## Priority order for Cowork

1. CL binomial price + spot price (mechanical, root-caused, ~15 min fix once script
   values are corrected and rebuilt).
2. CL conflict-of-interest disclosure (one sentence, non-negotiable).
3. ECI abstract/Table 2 contradiction + Bonferroni marking (both mechanical, both in
   the same section).
4. IL ratio reconciliation (requires a decision — which formula is "true" — before
   propagating the fix through every table).
5. Hayes attribution + Marthinsen & Gordon citation in CL (framing/citation work, not
   arithmetic).
6. WEI overlap in ECI (requires a data decision, not just a text fix).
7. Everything under "not independently confirmed" — worth a closer look before deciding
   whether action is needed, but don't treat as settled either way yet.
