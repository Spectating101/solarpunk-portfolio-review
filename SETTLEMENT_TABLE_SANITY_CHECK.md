# Sanity Check — §2.5 Settlement Table (physically-settled futures / certificates)

Requested by the Cowork revision pass on §2.5: verify the I-REC/tokenized-certificate
rows and the physically-settled-futures row against primary documentation rather than
resting on search summaries. Verified via live web search and direct document fetches,
July 2026.

## EEX / ECC power futures — CONFIRMED, real delivery obligation

- EEX power futures are exchange-traded and fungible (standardized 1 MW contracts).
  [EEX Power Futures](https://www.eex.com/en/markets/power/power-futures)
- Physical settlement is real and executed through EEX's clearing house, ECC, via a
  documented "cascading" delivery methodology (long-dated contracts progressively
  broken into shorter maturities down to delivery). [ECC](https://www.ecc.de/en/) /
  [Cascading Futures Explainer, ECC, 19.09.2025](https://www.eex.com/fileadmin/ECC/Downloads/Operations/Reports/Financial_Settlement_Reports/250919_Cascading_Explainer_ECC.pdf)
- ECC's own site confirms: "Clearing Members are not involved in the physical
  settlement process as delivery is processed by ECC Lux. They act as a payment agent
  and guarantor." [ECC Physical Settlement](https://www.ecc.de/en/operations/physical-settlement)
  — this confirms a genuine delivery obligation exists and is operationally handled,
  though the page doesn't quote the precise "who delivers what to whom" contract
  language; that would require ECC's Clearing Conditions document specifically, which
  was not retrieved.
- **Verdict: EEX is a safe, well-supported citation for "physically-settled power
  futures carry a genuine delivery obligation."**

## Nord Pool — NOT CONFIRMED as currently framed; needs a narrower claim

- Nord Pool's own contract specifications document — "Nordic and Baltic (EPAD) Power
  Futures Contracts," 14 August 2025 — covers System Price and EPAD futures across
  day/week/month/quarter/year maturities. Every single contract in this 21-page
  document is specified as **"Settlement: Cash settlement only."** The word "physical"
  does not appear anywhere in the document.
  [Contract Specifications PDF](https://www.nordpoolgroup.com/49649b/globalassets/download-center/rules-and-regulations/product-specifications-nordic-and-baltic-market-05.04.21.pdf)
- Nord Pool does appear to maintain a separate product category titled
  "Financial derivatives / Physically-settled contracts"
  (`nordpoolgroup.com/en/trading/Financial-derivatives/Physically-settled-contracts/`),
  but the page returned HTTP 403 and could not be verified directly.
- **Verdict: do not cite "Nord Pool" generically for physical settlement.** Either
  (a) drop Nord Pool from the table and rely on EEX alone as the physically-settled
  example, or (b) track down and cite the specific Nord Pool physically-settled
  product if it needs to stay — the generic claim as written is currently
  contradicted by Nord Pool's own most prominent contract family.

## I-REC / Tracking Standard — directionally supported, not a precise quote

- The foundation (rebranded from I-REC to Tracking Standard Foundation,
  trackingstandard.org) describes its certificates in terms of "claims of generation,
  ownership, and history" enabling "energy consumption choices" — language consistent
  with attribute attestation rather than a delivery obligation.
  [Tracking Standard Foundation](https://www.trackingstandard.org/)
- No page found gives a precise formal definition explicitly stating "this certificate
  carries no delivery obligation." Directionally supports the paper's claim; doesn't
  contradict it; not a clean citable quote.
- **Verdict: usable as a supporting citation with the caveat that it's inferential,
  not an explicit statement in the source.** For a stronger citation, the actual
  I-REC/Tracking Standard rulebook (not the marketing site) should be located.

## Tokenized certificates — supported by peer-reviewed literature

- IEEE: "Tokenizing Renewable Energy Certificates (RECs)—A Blockchain Approach for REC
  Issuance and Trading." [IEEE Xplore](https://ieeexplore.ieee.org/document/9994695/)
- Explicitly frames RECs (tokenized or not) as existing precisely because electricity
  from a renewable source is physically indistinguishable once injected into the grid
  — "impossible to physically trace the energy source to its point of consumption" —
  which is the structural reason the paper gives for why attribution and delivery
  can't be the same instrument. This is a real, citable, peer-reviewed source that
  directly supports the paper's structural argument, not just the descriptive claim.
- **Verdict: confirmed, and a stronger citation than what's likely currently in the
  draft — recommend using this IEEE paper directly in §2.5.**

## Net recommendation for §2.5

1. Keep EEX/ECC as the physically-settled example — it's solidly confirmed.
2. Either drop Nord Pool or replace the citation with the specific physically-settled
   product page once accessible — as currently framed, Nord Pool's own primary
   documentation contradicts the "physical delivery" claim for its main futures line.
3. Cite the IEEE tokenization paper for the structural argument (attribution ≠
   delivery because electricity is fungible at the grid) — it's a better source than
   a generic search summary and makes the same point the paper is making.
4. I-REC/Tracking Standard citation is fine as supporting color but flag internally
   that it's inferential, not a quoted definition — worth one more search pass against
   the actual standard/rulebook document (not the marketing homepage) if time allows.
