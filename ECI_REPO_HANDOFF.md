# ECI Repo Handoff — Section 1 Answered, Sections 2–10 Blocked

## 1. Authoritative project state

- **Repository**: `Spectating101/solarpunk-coin` (GitHub)
- **Current branch**: `thesis/cleanup-canonical-pdf`
- **Current commit**: `ab62cea8ace2f92d307cfd35ec208a9608180c16` (2026-07-25T03:40:10+08:00, "Make the corrected thesis PDF canonical, retire the pre-audit manuscript pipeline")
- **All local branches**: `thesis/cleanup-canonical-pdf` (current), `main`, `thesis/ceir-boundary-rewrite`, `feat/capsule-verifier`
- **21 additional remote-only branches** exist (agent/*, feat/*, docs/*); all fetched and searched — see below.

### Manuscript source location

`thesis_package/ENERGY_CIRCULATION_INDICATOR_PAPER_FINAL.docx` (and its rendered `.pdf`) is the authoritative manuscript source — it is the file that was actually edited to produce the current text. **Both files are untracked in git.** `*.pdf` is explicitly excluded by `.gitignore` line 169; the `.docx` was simply never `git add`ed.

Two earlier markdown drafts also exist and are also untracked: `thesis_package/ENERGY_CIRCULATION_INDICATOR_PAPER_V1.md`, `thesis_package/ENERGY_CIRCULATION_INDICATOR_PAPER_V2.md`.

### Does the PDF match the repo's latest analytical outputs?

There are no analytical outputs in the repo to compare it against — see below. The PDF's numbers cannot be checked against repository data because no such data exists in the repository.

### Every ECI-related file that exists anywhere in this repository

```
thesis_package/ENERGY_CIRCULATION_INDICATOR_PAPER_FINAL.docx   [UNTRACKED]
thesis_package/ENERGY_CIRCULATION_INDICATOR_PAPER_FINAL.pdf    [UNTRACKED, gitignored]
thesis_package/ENERGY_CIRCULATION_INDICATOR_PAPER_V1.md        [UNTRACKED]
thesis_package/ENERGY_CIRCULATION_INDICATOR_PAPER_V2.md        [UNTRACKED]
thesis_package/energy_indicator_figures/                       [UNTRACKED]
  fig1_taiwan_semiconductor_share.png
  fig2_semiconductor_vs_economy_growth.png
  fig3_granger_causality_electricity.png
  fig4_crypto_specifications_summary.png
```

That is the complete list. There is no script, dataset, table export, appendix file, or generation log for ECI anywhere in this repository, on any branch, at any point in its commit history.

### What was searched, to rule this out rather than assume it

- `git log --all --diff-filter=A --name-only` across every local branch and all 21 fetched remote branches, for filename patterns: `*energy_circulation*`, `*energy_indicator*`, `*defillama*`, `*stablecoin*`, `*taipower*` — zero results at any point in history, on any branch.
- Working-tree content search (`grep -rl`) for `defillama`, `taipower`, `data.gov.tw` across all `.py`, `.csv`, `.json`, `.js`, `.ipynb` files in the repo — zero results.
- The four PNGs in `energy_indicator_figures/` are finished chart images, not data or code. No notebook, script, or CSV produced them that exists in this repository.

### Uncommitted or locally generated files required for reproduction

All of them. The manuscript itself is uncommitted. There is no reproduction pipeline to be missing files *from* — the pipeline itself was never checked in. The underlying data pulls (DeFi/stablecoin activity, FRED series, Taiwan Taipower sector electricity, WEI construction) that produced the paper's 44 specifications, Granger tests, and Taiwan figures were evidently run in an ephemeral session (live API/web queries) and never saved back to this repository in any form — no raw pull, no cleaned intermediate, no analysis script, no notebook.

## What this means for the rest of the requested audit

Sections 2 through 10 of the original request each depend on locating a script, dataset, or generation log to audit against. Based on the search above, that material does not exist in this repository. Concretely:

- **§2 claim-to-code map**: cannot be built — there is no code to map claims to. Every row would read "no script found in repo."
- **§3 44-specification export**: cannot be reproduced from repo contents — no source data for DeFi TVL, stablecoin supply, or the comparison series exists here.
- **§4 crypto conclusions audit**: same blocker.
- **§5 electricity–real-activity audit**: same blocker — FRED series identifiers and Granger results are stated in the manuscript prose only; no pull or script exists to verify against.
- **§6 Taiwan semiconductor dataset audit**: same blocker — no Taipower/data.gov.tw pull exists in the repo to check units, revisions, or the 26.2%/26.4% discrepancy against.
- **§7 December 2025 anomaly**: same blocker — cannot distinguish "provisional" from "anomalous" without the underlying monthly series, which isn't here.
- **§8 figure/table regeneration**: the four PNGs are final images with no generating script in the repo; cannot regenerate or check for hard-coded values.
- **§9 citation audit**: this part IS answerable from the manuscript text alone (references don't require underlying data) and is a reasonable ask on its own.
- **§10 confidence-score provenance**: also answerable from manuscript text/author recall alone, not blocked by missing data.
- **§11 relationship to Constrained Ledger**: answerable by reading both manuscripts; not blocked.
- **§12 deliverables**: most of the requested CSVs (`eci_all_44_specs.csv`, `eci_granger_full_results.csv`, `eci_taiwan_monthly_clean.csv`) cannot be produced — there is no source to extract them from.

## Recommendation

Don't run the full request against this repository as-is. Two real options:

1. **If the original analysis still exists somewhere** (a prior chat session, a local file outside this repo, a notebook on another machine) — locate and commit it first. Then this audit becomes fully answerable.
2. **If it doesn't exist anywhere anymore** — the honest path is to treat every quantitative claim in the ECI manuscript as currently unverifiable-by-reproduction (distinct from "wrong" — it may well be correct, it just cannot currently be checked against source), and either rebuild the underlying pulls from scratch (re-fetch DefiLlama/FRED/Taipower data, rerun the 44 specifications, regenerate the Granger tests and figures, commit all of it this time) or scope the paper down to only the claims that can be re-derived.

Sections 9, 10, and 11 of the original request can proceed immediately regardless of which path is chosen, since they don't depend on missing data.
