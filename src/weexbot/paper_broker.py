"""Paper broker (Faza 2) - gradi naloge iz signala BEZ pravog WEEX API-ja.

Za futures poziciju gradimo tri naloga:
  - ENTRY_LIMIT  : ulaz (BUY za LONG, SELL za SHORT)
  - STOP_LOSS    : zastitni stop (reduce-only, suprotna strana)
  - TAKE_PROFIT  : prvi TP (reduce-only, suprotna strana)

U Fazi 3 ovaj modul dobiva stvarni WEEX REST/WS adapter; potpis ostaje isti.
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import Side, Signal
from .risk import PositionPlan


@dataclass
class PaperOrder:
    client_order_id: str   # idempotentni kljuc (UNIQUE u bazi)
    symbol: str
    otype: str             # ENTRY_LIMIT | STOP_LOSS | TAKE_PROFIT
    side: str              # BUY | SELL
    price: float | None
    quantity: float
    reduce_only: bool


def _entry_side(side: Side) -> str:
    return "BUY" if side == Side.LONG else "SELL"


def _exit_side(side: Side) -> str:
    return "SELL" if side == Side.LONG else "BUY"


def build_orders(signal: Signal, plan: PositionPlan, weex_symbol: str,
                 key: str) -> list[PaperOrder]:
    """key = jedinstveni prefiks (najcesce message_id) za client_order_id."""
    qty = plan.quantity
    entry_side = _entry_side(signal.side)
    exit_side = _exit_side(signal.side)

    orders = [
        PaperOrder(f"{key}-ENTRY", weex_symbol, "ENTRY_LIMIT", entry_side,
                   signal.entry, qty, reduce_only=False),
        PaperOrder(f"{key}-SL", weex_symbol, "STOP_LOSS", exit_side,
                   signal.stop, qty, reduce_only=True),
    ]
    if signal.take_profits:
        orders.append(
            PaperOrder(f"{key}-TP1", weex_symbol, "TAKE_PROFIT", exit_side,
                       signal.take_profits[0].price, qty, reduce_only=True)
        )
    return orders
