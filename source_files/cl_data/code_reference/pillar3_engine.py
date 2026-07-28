"""
Off-chain risk and settlement utilities for Pillar 3 energy-backed options.

This module does not do on-chain work. It aggregates oracle sources, computes
payoffs, and simulates basic margin logic for European calls/puts on an energy
index. Use it to sanity-check term-sheet parameters before pushing them on-chain.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from statistics import median
from typing import List, Optional, Tuple


# ------------------------
# Oracle aggregation
# ------------------------

@dataclass
class OracleSource:
    value: float          # quoted index value, e.g., $/kWh
    timestamp: float      # epoch seconds
    weight: float = 1.0   # relative weight


def weighted_median(sources: List[OracleSource]) -> float:
    """Compute weighted median of source values."""
    sorted_items = sorted(((s.value, s.weight) for s in sources), key=lambda x: x[0])
    total_weight = sum(w for _, w in sorted_items)
    accum = 0.0
    for value, weight in sorted_items:
        accum += weight
        if accum >= total_weight / 2:
            return value
    return sorted_items[-1][0]


def aggregate_index(
    sources: List[OracleSource],
    now: Optional[float] = None,
    max_staleness_secs: int = 24 * 3600,
    max_dev_sigma: float = 3.0,
    hist_window: Optional[List[float]] = None,
) -> Tuple[Optional[float], str]:
    """
    Aggregate oracle sources with staleness and deviation checks.

    Returns (index, status):
      - index: aggregated value or None if rejected
      - status: "OK", "STALE", "INSUFFICIENT_SOURCES", or "OUT_OF_BOUNDS"
    """
    if now is None:
        now = time.time()
    valid = [s for s in sources if now - s.timestamp <= max_staleness_secs]
    if len(valid) < 2:
        return None, "INSUFFICIENT_SOURCES"

    idx = weighted_median(valid)

    if hist_window:
        m = median(hist_window)
        abs_dev = [abs(x - m) for x in hist_window]
        mad = median(abs_dev) if abs_dev else 0.0
        if mad > 0:
            # Using median absolute deviation as a robust proxy for sigma
            if abs(idx - m) > max_dev_sigma * mad:
                return None, "OUT_OF_BOUNDS"

    return idx, "OK"


# ------------------------
# Contract and margin logic
# ------------------------

@dataclass
class Series:
    expiry: float           # epoch seconds
    strike: float           # $/kWh
    is_call: bool
    notional_kwh: float = 1000.0


@dataclass
class Position:
    qty: float              # +long, -short (in contracts)
    margin: float           # current margin balance in USDC
    status: str = "ACTIVE"  # ACTIVE, MARGIN_CALL, LIQUIDATED


def payoff(series: Series, index: float) -> float:
    """Intrinsic payoff per contract at settlement index."""
    intrinsic = max(index - series.strike, 0.0) if series.is_call else max(series.strike - index, 0.0)
    return intrinsic * series.notional_kwh


def calc_mtm(series: Series, index: float, entry_index: float) -> float:
    """
    Mark-to-market PnL per contract relative to an entry index.
    Positive for longs when index moves favorably.
    """
    return payoff(series, index) - payoff(series, entry_index)


def initial_margin_from_var(var_payoff: float, buffer: float = 1.5) -> float:
    """Initial margin as a multiple of VaR (e.g., 1.5x VaR99 payoff)."""
    return buffer * var_payoff


def check_margin(position: Position, mtm: float, im: float, maintenance_ratio: float = 0.75) -> str:
    """
    Evaluate margin status given current MTM and initial margin requirement.
    Returns status string.
    """
    equity = position.margin + position.qty * mtm
    if equity < maintenance_ratio * im * abs(position.qty):
        if equity < 0:
            return "LIQUIDATE"
        return "MARGIN_CALL"
    return "OK"


def liquidate(position: Position, series: Series, index: float, penalty_rate: float = 0.01) -> Tuple[float, float]:
    """
    Liquidate position at current index.
    Returns (payout_to_user, penalty_to_insurance).
    """
    intrinsic = payoff(series, index) * position.qty
    equity = position.margin + intrinsic
    penalty = max(0.0, equity) * penalty_rate
    payout = equity - penalty
    position.status = "LIQUIDATED"
    return payout, penalty


# ------------------------
# Example usage
# ------------------------

if __name__ == "__main__":
    # Example: aggregate three sources
    now = time.time()
    sources = [
        OracleSource(value=0.055, timestamp=now, weight=0.4),
        OracleSource(value=0.054, timestamp=now, weight=0.4),
        OracleSource(value=0.056, timestamp=now - 1000, weight=0.2),
    ]
    idx, status = aggregate_index(sources, now=now, hist_window=[0.054, 0.055, 0.056, 0.055])
    print(f"Aggregated index: {idx}, status: {status}")

    # Example: margin check for a 1-lot long call
    series = Series(expiry=now + 90 * 86400, strike=0.0525, is_call=True, notional_kwh=1000)
    position = Position(qty=1.0, margin=0.40)  # USDC

    entry_index = 0.0525
    current_index = idx if idx else entry_index

    # Suppose VaR99 from your grid is 0.264 (see margin_stress_table.csv row with S0=0.0525, sigma=1.89)
    im_required = initial_margin_from_var(0.264)
    mtm = calc_mtm(series, current_index, entry_index)
    m_status = check_margin(position, mtm, im_required)
    print(f"MTM: {mtm:.4f}, equity: {position.margin + position.qty * mtm:.4f}, status: {m_status}")

    if m_status == "LIQUIDATE":
        payout, penalty = liquidate(position, series, current_index)
        print(f"Liquidated. Payout: {payout:.4f}, penalty to fund: {penalty:.4f}")

