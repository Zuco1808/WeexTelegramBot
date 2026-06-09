"""Risk engine (Faza 1, demo) - position sizing po fiksnom % rizika.

Velicina pozicije ne ovisi o leverage-u, nego o udaljenosti entry<->stop:
    rizik_USDT = kapital * risk_pct
    kolicina   = rizik_USDT / |entry - stop|
Leverage utjece samo na potrebnu marginu i likvidaciju.
"""
from __future__ import annotations

from dataclasses import dataclass

from .config import CAPITAL_USDT, RISK_PCT_SCALP


@dataclass
class PositionPlan:
    quantity: float        # kolicina u baznoj valuti (npr. ETH, BTC)
    notional: float        # vrijednost pozicije u USDT
    margin: float | None   # potrebna margina uz dani leverage
    risk_usdt: float       # koliko gubimo ako SL bude pogoden


def plan_position(
    entry: float,
    stop: float,
    leverage: float | None,
    capital: float = CAPITAL_USDT,
    risk_pct: float = RISK_PCT_SCALP,
) -> PositionPlan | None:
    dist = abs(entry - stop)
    if dist == 0:
        return None
    risk_usdt = capital * risk_pct
    qty = risk_usdt / dist
    notional = qty * entry
    margin = (notional / leverage) if leverage else None
    return PositionPlan(quantity=qty, notional=notional, margin=margin, risk_usdt=risk_usdt)
