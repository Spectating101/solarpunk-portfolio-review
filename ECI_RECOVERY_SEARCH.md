# ECI Recovery Search — Results

Searched: full git history (all local + all 21 fetched remote branches), real shell
history (`.bash_history`), Gemini CLI history (all project-scoped and orphaned session
dirs), Claude Code session transcripts for this project, VS Code and Cursor local file
History (all entries, content-searched not just filename-searched), Cursor
workspaceStorage, `/tmp`, `/var/tmp`, Trash, and a separate sibling project
(`Molina-Optiplex/Sharpe-Renaissance`) that shares some vocabulary (DeFiLlama,
Taipower, "semiconductor") but was ruled out — zero hits for the two most specific,
false-positive-proof identifiers (`IPG2211A2N`, exact phrase "Weekly Economic Index").

## Verdict: **Partial components recovered.**

### Recovered

**Taiwan Taipower sector-electricity data — full recovery.**
- Location found: `/tmp/taipower_data/` and `/tmp/taipower2.zip` (both now copied into
  `thesis_package/eci_recovered_data/` — `/tmp` is not a safe permanent location and
  could be cleared on reboot).
- Content: `行業別售電_2021.csv` through `_2025.csv` — monthly electricity sales (度/kWh)
  by industry sub-sector, 2021–2025, plus schema files and a manifest. Confirmed as
  genuine Taipower/data.gov.tw open data by structure and Chinese-language industry
  classification codes (行業別大類/中類/小類), matching the paper's stated source exactly.
- Semiconductor manufacturing isolated at code `261 半導體製造業` under
  `26 電子零組件製造業` under `C.製造業` — verified no double-counting risk (no redundant
  subtotal row exists at the parent level).
- **Independently recomputed the entire semiconductor-share time series from this raw
  data and checked it against every number printed in the manuscript:**

  | Manuscript claim | My recomputation | Match |
  |---|---|---|
  | Jan 2021: 18.4% | 18.39% | ✓ |
  | Dec 2022: 22.1% | 22.08% | ✓ |
  | Dec 2023: 23.7% | 23.73% | ✓ |
  | Dec 2024: 24.2% | 24.24% | ✓ |
  | Oct 2025 (abstract): 26.4% | 26.36% | ✓ |
  | Oct 2025 (Figure 3, before fix): 26.2% | 26.36% | ✗ — Figure 3 was wrong |
  | Nov 2025 (unlabeled): — | 26.25% | — |
  | Dec 2025 semiconductor Nov→Dec: −35.0% | −35.0% | ✓ exact |
  | Dec 2025 whole-economy Nov→Dec: −13.9% | −13.9% | ✓ exact |
  | 2021 Nov→Dec: sc +1.8%, econ −0.2% | sc +1.8%, econ −0.2% | ✓ exact |
  | 2022 Nov→Dec: sc −3.9%, econ −2.4% | sc −3.9%, econ −2.4% | ✓ exact |
  | 2023 Nov→Dec: sc +3.5%, econ −0.0% | sc +3.5%, econ −0.0% | ✓ exact |
  | 2024 Nov→Dec: sc −2.7%, econ −3.4% | sc −2.7%, econ −3.4% | ✓ exact |
  | 2022 annual growth: sc +10.8%, econ +1.3% | sc +10.8%, econ +1.3% | ✓ exact |
  | 2023 annual growth: sc +4.5%, econ −2.7% | sc +4.5%, econ −2.7% | ✓ exact |
  | 2024 annual growth: sc +5.8%, econ +2.1% | sc +5.8%, econ +2.1% | ✓ exact |
  | 2025 annual growth: sc +5.4%, econ −0.3% | sc +5.4%, econ −0.3% | ✓ exact |

  Every number in the manuscript's Taiwan analysis is now independently verified
  against real recovered source data, with one confirmed and fixed exception:
  **Figure 3's "26.2% (Oct 2025 peak)" annotation was wrong — the true October 2025
  value is 26.36% (rounds to 26.4%, matching the abstract and Table 4, which were both
  already correct). 26.2% appears to be November 2025's value (26.25%), plotted under
  the October label — an apparent off-by-one-month bug in the original figure
  generation.** Figure 3 has been regenerated from the verified data and corrected;
  see `thesis_package/eci_recovered_data/fig3_corrected.png`, already embedded in the
  manuscript.

- Clean, full-precision export produced: `thesis_package/eci_recovered_data/eci_taiwan_monthly_clean.csv`
  (date, year, month, total_kwh, semiconductor_kwh, semiconductor_share_pct — 60 months,
  Jan 2021–Dec 2025).

### Not recovered

**The 44 crypto specifications, Granger-causality regression code, and WEI
construction — nothing found anywhere on the machine.** No DeFiLlama pull, no FRED
pull, no regression script, no notebook. This part of the analysis is not just
uncommitted — it does not appear to exist in any recoverable form (no shell history,
no editor local-history snapshot, no session transcript, no orphaned temp file). If it
exists, it is on infrastructure this search could not reach (a separate machine, a
cloud notebook, a chat session in a tool with no local trace).

**PNG metadata check** on the four original figure files: no creation-software tags or
source-path references present (standard matplotlib output strips this by default);
metadata inspection did not narrow down where they were generated.

## What this means, concretely

The Taiwan semiconductor section (§5 of the manuscript, roughly a third of the paper's
total empirical content) is now fully reproducible and independently verified — real
data, checked line by line, one real error found and fixed. The crypto-specifications
section (§3) and the electricity/WEI Granger-causality section (§4) remain exactly as
uncertain as before this search: correct or not, there is currently no way to check,
and no further searching of this machine is likely to change that. Rebuilding those
two sections from scratch (re-pull DeFiLlama/FRED data, rerun the 44 specifications,
regenerate the Granger tests, commit everything this time) is the only path to the
same level of confidence §5 now has.
