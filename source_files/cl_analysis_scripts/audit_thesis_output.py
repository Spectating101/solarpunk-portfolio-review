#!/usr/bin/env python3
"""
DEPRECATED (2026-07-25). Default targets (output/reading/full/THESIS_GROUNDED.pdf,
THESIS_GROUNDED_MANUSCRIPT.md) are archived under
thesis_package/_archive/superseded_2026-07/ — that manuscript states the retired
Chapter 3 CEIR claim (see THESIS_SOURCE_OF_TRUTH.md). The canonical thesis is now
maintained directly: energy_constraint_thesis_final_submission.pdf (repo root),
with no build pipeline behind it. Mechanical checks below (banned phrases,
duplicate refs) may still be useful if pointed at a real PDF/manuscript, but a
passing run says nothing about Chapter 3's empirical accuracy.

Audit built thesis PDF and manuscript for submission-quality issues.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent
ROOT = PKG.parent
DEFAULT_PDF = PKG / "output" / "reading" / "full" / "THESIS_GROUNDED.pdf"
DEFAULT_MD = PKG / "THESIS_GROUNDED_MANUSCRIPT.md"

BANNED_IN_PDF = [
    (r"npm run", "developer command in PDF body"),
    (r"python thesis_package", "developer command in PDF body"),
    (r"Update field in Word", "Word TOC placeholder"),
    (r"<!-- INJECT_", "unexpanded inject marker"),
    (r"Figure Figure", "duplicate figure caption"),
    (r"^Figure$", "orphan Figure caption line"),
    (r"^#Metrics", "malformed evidence intro heading"),
    (r"Bank for International Settlements\. \(2023\).*https://www\.bis\.org/publ/arpdf/ar2023e3", "duplicate BIS 2023 entry"),
    (r"Cambridge Centre for Alternative Finance\. \(n\.d\.-a\).*\n.*Cambridge Centre for Alternative Finance\. \(n\.d\.-a\)", "duplicate Cambridge n.d.-a label"),
]


def audit_markdown(md_path: Path) -> list[str]:
    issues: list[str] = []
    if not md_path.exists():
        return [f"missing manuscript: {md_path}"]
    text = md_path.read_text(encoding="utf-8")
    if "<!-- INJECT_" in text:
        issues.append("manuscript contains unexpanded INJECT markers")
    if text.count("bis.org/publ/arpdf/ar2023e3") > 1:
        issues.append("duplicate BIS 2023 reference URL in manuscript")
    refs = text.split("## References", 1)[-1] if "## References" in text else ""
    if refs.count("Cambridge Centre for Alternative Finance. (n.d.-a)") > 1:
        issues.append("duplicate Cambridge n.d.-a label in references")
    paras = [p.strip() for p in re.split(r"\n\n+", text) if len(p.strip()) > 80]
    from collections import Counter

    dupes = [p for p, n in Counter(paras).items() if n > 1]
    if dupes:
        issues.append(f"{len(dupes)} exact duplicate paragraph(s) in manuscript")
    return issues


def audit_pdf(pdf_path: Path) -> list[str]:
    issues: list[str] = []
    if not pdf_path.exists():
        return [f"missing PDF: {pdf_path}"]
    try:
        import fitz
    except ImportError:
        return ["pymupdf not installed; skip PDF audit"]

    doc = fitz.open(str(pdf_path))
    try:
        for page_idx in range(len(doc)):
            text = doc[page_idx].get_text("text")
            page = page_idx + 1
            for pattern, label in BANNED_IN_PDF:
                if re.search(pattern, text, re.MULTILINE):
                    issues.append(f"page {page}: {label}")
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            if page > 2 and len(lines) <= 1 and len(text) < 80:
                issues.append(f"page {page}: near-empty page ({lines})")
            fig_caps = sum(1 for ln in lines if re.match(r"^Figure \d", ln))
            body = sum(
                1
                for ln in lines
                if len(ln) > 50
                and not ln.startswith("Figure")
                and not re.match(r"^\d+$", ln)
            )
            if fig_caps >= 2 and body == 0 and len(lines) <= 4:
                issues.append(f"page {page}: caption-only page (check figure pagination)")
    finally:
        doc.close()
    return issues


def main() -> int:
    md_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_MD
    pdf_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_PDF

    issues = audit_markdown(md_path) + audit_pdf(pdf_path)
    if issues:
        print("thesis_audit_issues:")
        for item in issues:
            print(f"  - {item}")
        return 1
    print("thesis_audit_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
