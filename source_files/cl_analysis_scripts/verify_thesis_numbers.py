#!/usr/bin/env python3
"""
DEPRECATED (2026-07-25). check_ceir() below asserts the retired Chapter 3 claim
("Chow p-value should indicate break") that CEIR_FINAL_DIAGNOSIS.md (2026-07-10)
disproved via negative controls and the preferred robust joint-Wald test (p ~ 0.13,
does not reject stability). This script still reports thesis_verify_ok because it
checks against the wrong ground truth — do not trust a passing run as evidence the
thesis is accurate. See THESIS_SOURCE_OF_TRUTH.md for the corrected numbers.

The manuscript this script validated (THESIS_GROUNDED_MANUSCRIPT.md) is archived
under thesis_package/_archive/superseded_2026-07/. The canonical thesis is now
maintained directly, with no build/verify pipeline: energy_constraint_thesis_final_submission.pdf.

Kept for reference only (pricing/SPK checks below are still factually fine) — do
not treat check_ceir()'s pass/fail as validation of Chapter 3.

---
Verify thesis canonical numbers against repo artifacts.

Run after options_pricing.py / ceir_regression.py / generate_thesis_figures.py:
    python thesis_package/verify_thesis_numbers.py

Exits 0 if all checks pass; prints THESIS_NUMBERS_MANIFEST.md summary.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PKG = Path(__file__).resolve().parent
ROOT = PKG.parent
RESULTS = PKG / "empirical_results"
FIGURES = RESULTS / "figures"
SPK_RUNTIME = ROOT / "state" / "runtime" / "spk_v1.json"
MANIFEST_PATH = PKG / "THESIS_NUMBERS_MANIFEST.md"

CHAPTER_GLOBS = list(PKG.glob("CHAPTER_*_GROUNDED_DRAFT.md"))


def _round4(x: float) -> float:
    return round(float(x), 4)


def check_ceir() -> list[str]:
    issues: list[str] = []
    summary = pd.read_csv(RESULTS / "ceir_analysis_summary.csv")
    row = summary.iloc[0]

    if row["Pre_ban_CEIR_coef"] >= 0:
        issues.append("CEIR pre-ban beta should be negative")
    if abs(row["Pre_ban_CEIR_coef"]) < 0.1:
        issues.append(f"CEIR pre-ban beta unexpectedly small: {row['Pre_ban_CEIR_coef']}")
    if abs(row["Post_ban_CEIR_coef"]) > abs(row["Pre_ban_CEIR_coef"]):
        issues.append(
            "CEIR post-ban |beta| should not exceed pre-ban in current spec "
            f"(pre={row['Pre_ban_CEIR_coef']}, post={row['Post_ban_CEIR_coef']})"
        )
    if float(row["Chow_pvalue"]) > 0.05:
        issues.append(f"Chow p-value should indicate break: {row['Chow_pvalue']}")

    diff = pd.read_csv(RESULTS / "ceir_analysis_summary_diff.csv").iloc[0]
    if float(diff["Pre_ban_p_hac"]) < 0.05 or float(diff["Post_ban_p_hac"]) < 0.05:
        issues.append("Differenced CEIR should be insignificant pre and post")

    trading = json.loads((RESULTS / "ceir_trading_rule_summary.json").read_text())
    for key in ("total_return_strategy_pct", "total_return_buyhold_pct", "sharpe_strategy", "sharpe_buyhold"):
        if key not in trading:
            issues.append(f"Trading summary missing key: {key}")
    if trading.get("total_return_strategy_pct", 0) >= trading.get("total_return_buyhold_pct", 1):
        issues.append("Trading rule should underperform buy-and-hold on total return")

    panel = pd.read_csv(RESULTS / "bitcoin_ceir_analysis_ready.csv", parse_dates=["Date"])
    fwd = panel["Price"].shift(-30) / panel["Price"] - 1
    if panel["Returns_forward"].corr(fwd) < 0.99:
        issues.append(
            "Returns_forward does not match 30-day forward return — run ceir_regression.py --refresh-panel"
        )

    return issues


def check_pricing() -> list[str]:
    issues: list[str] = []
    xl = pd.read_csv(RESULTS / "cross_location_pricing.csv")
    tw = xl[xl["Location"] == "Taiwan"].iloc[0]
    b, mc = float(tw["Call (Binomial)"]), float(tw["Call (MC)"])
    if abs(b - 0.01917) > 0.0001:
        issues.append(f"Taiwan binomial call: {b} (expected ~0.01917)")
    if abs(mc - 0.01957) > 0.0001:
        issues.append(f"Taiwan MC call: {mc} (expected ~0.01957)")
    gap = abs(mc - b) / b * 100
    if abs(gap - 2.1) > 0.3:
        issues.append(f"Taiwan method gap: {gap:.2f}% (expected ~2.1%)")

    margin = pd.read_csv(RESULTS / "margin_stress_table.csv")
    if "Initial_margin_1.5x" not in margin.columns:
        issues.append("margin_stress_table.csv missing Initial_margin_1.5x — rerun options_pricing.py")
    else:
        tw_m = margin[(margin["S0"] == 0.0525) & (margin["sigma"] == 1.89)]
        if tw_m.empty:
            issues.append("margin_stress_table missing Taiwan σ=1.89 row")
        elif abs(float(tw_m.iloc[0]["Initial_margin_1.5x"]) - 0.633) > 0.02:
            issues.append(
                f"Taiwan margin at σ=1.89: {tw_m.iloc[0]['Initial_margin_1.5x']} (expected ~0.633)"
            )

    oracle = pd.read_csv(RESULTS / "oracle_tolerance.csv")
    tw_o = oracle[oracle["Location"] == "Taiwan"].iloc[0]
    if abs(float(str(tw_o["Max err @ VR≥95%"]).replace("%", "")) - 21.7) > 0.2:
        issues.append(f"Taiwan oracle tolerance mismatch: {tw_o['Max err @ VR≥95%']}")

    return issues


def check_spk() -> list[str]:
    issues: list[str] = []
    if not SPK_RUNTIME.exists():
        issues.append(f"Missing runtime: {SPK_RUNTIME}")
        return issues
    spk = json.loads(SPK_RUNTIME.read_text())
    on_chain = spk.get("on_chain", {})
    genesis = spk.get("genesis", {}).get("metrics", {})
    supply = round(float(on_chain.get("total_supply_spk", 0)))
    if supply not in (5498, 5499, 5500):
        issues.append(f"SPK supply ~{supply} (expected ~5499)")
    if int(genesis.get("network_payment_count", 0)) != 21:
        issues.append(f"SPK payments: {genesis.get('network_payment_count')} (expected 21)")
    settled = float(genesis.get("total_settled_spk", 0))
    if abs(settled - 442.0) > 1.0:
        issues.append(f"SPK settled: {settled} (expected 442)")
    if spk.get("monetary_policy", {}).get("peg_enabled", True) is not False:
        issues.append("SPK peg should be off in runtime")
    return issues


def check_figures() -> list[str]:
    issues: list[str] = []
    manifest = json.loads((FIGURES / "manifest.json").read_text())
    expected = manifest.get("figures", [])
    for rel in expected:
        path = PKG / rel
        if not path.exists():
            issues.append(f"Missing figure: {rel}")

    img_refs = set()
    for ch in CHAPTER_GLOBS:
        text = ch.read_text(encoding="utf-8")
        for m in re.finditer(r"!\[[^\]]*\]\((empirical_results/figures/[^)]+)\)", text):
            img_refs.add(m.group(1))
    for ref in sorted(img_refs):
        if not (PKG / ref).exists():
            issues.append(f"Chapter references missing figure: {ref}")
    return issues


def write_manifest(ceir_row, pricing_tw, spk: dict | None, issues: list[str]) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    status = "PASS" if not issues else f"FAIL ({len(issues)} issues)"
    trading = json.loads((RESULTS / "ceir_trading_rule_summary.json").read_text())
    lines = [
        "# Thesis Numbers Manifest",
        "",
        f"**Generated:** {now}  ",
        f"**Verification:** {status}  ",
        f"**Regenerate:** `npm run thesis:verify` or `npm run thesis:figures`",
        "",
        "Canonical values below are what Chapters 3–5 should cite. Prose may round;",
        "tables and at-a-glance boxes should match within ±0.01 unless noted.",
        "",
        "## Chapter 3 — CEIR (Bitcoin)",
        "",
        "| Item | Value | Source |",
        "|------|------:|--------|",
        f"| Pre-ban N | {int(ceir_row['Pre_ban_N'])} | `ceir_analysis_summary.csv` |",
        f"| Post-ban N | {int(ceir_row['Post_ban_N'])} | same |",
        f"| Pre-ban β (log CEIR) | {ceir_row['Pre_ban_CEIR_coef']:.4f} | same |",
        f"| Post-ban β (log CEIR) | {ceir_row['Post_ban_CEIR_coef']:.4f} | same |",
        f"| Chow p-value | {ceir_row['Chow_pvalue']:.2e} | same |",
        f"| Trading rule | {trading['total_return_strategy_pct']:.1f}% vs {trading['total_return_buyhold_pct']:.0f}% buy-and-hold; Sharpe {trading['sharpe_strategy']:.2f} vs {trading['sharpe_buyhold']:.2f} | `ceir_trading_rule_summary.json` |",
        "",
        "## Chapter 4 — Pricing (Taiwan base)",
        "",
        "| Item | Value | Source |",
        "|------|------:|--------|",
        f"| S₀ | $0.0525/kWh | `options_pricing.py` |",
        f"| σ | 189% | same |",
        f"| Binomial call | ${_round4(pricing_tw['Call (Binomial)']):.5f}/kWh | `cross_location_pricing.csv` |",
        f"| Monte Carlo call | ${_round4(pricing_tw['Call (MC)']):.5f}/kWh | same |",
        f"| Method gap | {abs(pricing_tw['Call (MC)'] - pricing_tw['Call (Binomial)']) / pricing_tw['Call (Binomial)'] * 100:.2f}% | same |",
        "| Strike convention | K = S₀ per location (ATM) | Table 4.2 |",
        "| Taiwan margin (1.5× VaR₉₉) | ~$0.63/kWh | `margin_stress_table.csv` |",
        "",
        "## Chapter 5 — SPK v1 (Sepolia runtime)",
        "",
    ]
    if spk:
        m = spk.get("genesis", {}).get("metrics", {})
        oc = spk.get("on_chain", {})
        lines.extend(
            [
                "| Item | Value | Source |",
                "|------|------:|--------|",
                f"| Total supply | {oc.get('total_supply_spk', 'n/a')} SPK | `state/runtime/spk_v1.json` |",
                f"| Settled | {m.get('total_settled_spk', 'n/a')} SPK | same |",
                f"| Network payments | {m.get('network_payment_count', 'n/a')} | same |",
                f"| Circulation share | {m.get('circulation_share_percent', 'n/a')}% | same |",
                f"| Peg enabled | {spk.get('monetary_policy', {}).get('peg_enabled', 'n/a')} | same |",
                f"| Synced at | {spk.get('synced_at', 'n/a')} | same |",
                "",
            ]
        )
    else:
        lines.append("*Runtime file not found — run `npm run foundation:sync` when RPC available.*\n")

    lines.extend(
        [
            "## Figures (embedded in DOCX)",
            "",
            "| Figure | File | Chapter |",
            "|--------|------|---------|",
            "| CEIR timeline | `ceir_timeline.png` | 3 |",
            "| CEIR forward returns (illustrative) | `ceir_forward_returns.png` | 3 |",
            "| Trading rule negative result | `trading_rule_comparison.png` | 3 |",
            "| Cross-location pricing | `cross_location_pricing.png` | 4 |",
            "| Binomial convergence | `binomial_convergence.png` | 4 |",
            "| Margin stress | `margin_stress_taiwan.png` | 4 |",
            "",
            "## Literature (Ch 2)",
            "",
            "No automated numeric check. Ch 2 cites Kydland & Prescott, Barro & Gordon, Bordo,",
            "Eichengreen, Hayes, Liu & Tsyvinski, Black–Scholes, CRR, Bessembinder & Lemmon,",
            "Cong & He, BIS (2023), Chainlink oracle docs. Merged at build into final References.",
            "",
        ]
    )
    if issues:
        lines.extend(["## Issues", ""] + [f"- {i}" for i in issues] + [""])
    MANIFEST_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    issues: list[str] = []
    issues.extend(check_ceir())
    issues.extend(check_pricing())
    issues.extend(check_figures())
    issues.extend(check_spk())

    ceir_row = pd.read_csv(RESULTS / "ceir_analysis_summary.csv").iloc[0]
    pricing_tw = pd.read_csv(RESULTS / "cross_location_pricing.csv")
    pricing_tw = pricing_tw[pricing_tw["Location"] == "Taiwan"].iloc[0]
    spk = json.loads(SPK_RUNTIME.read_text()) if SPK_RUNTIME.exists() else None

    write_manifest(ceir_row, pricing_tw, spk, issues)

    if issues:
        print("thesis_verify_FAIL")
        for i in issues:
            print(f"  - {i}")
        print(f"wrote {MANIFEST_PATH.relative_to(ROOT)}")
        return 1

    print("thesis_verify_ok")
    print(f"wrote {MANIFEST_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
