"""Pipeline (Faza 2): poruka -> parse -> persist -> (ako TRADABLE) paper nalozi.

Idempotentnost preko message_id: ista poruka obradjena dvaput NE stvara duplu
poziciju. Sve nepoznato (UNKNOWN chatter) se ignorira; ostalo se sprema radi
buduceg Trade Managera (Faza 6).
"""
from __future__ import annotations

from dataclasses import dataclass

from .config import (
    CAPITAL_USDT,
    MAX_OPEN_POSITIONS,
    MAX_PORTFOLIO_MARGIN_PCT,
    RISK_PCT_SCALP,
)
from .db import Database
from .models import SignalKind, TradeStatus
from .paper_broker import build_orders
from .parser import parse
from .risk import plan_position
from .symbols import resolve_symbol


@dataclass
class ProcessResult:
    message_id: str
    kind: str
    status: str
    action: str                 # IGNORED | STORED | SKIPPED_DUPLICATE | SKIPPED_SYMBOL | POSITION_PLANNED
    position_id: int | None = None
    note: str = ""


class Pipeline:
    def __init__(self, db: Database, capital: float = CAPITAL_USDT,
                 risk_pct: float = RISK_PCT_SCALP,
                 max_open: int = MAX_OPEN_POSITIONS,
                 max_margin_pct: float = MAX_PORTFOLIO_MARGIN_PCT):
        self.db = db
        self.capital = capital
        self.risk_pct = risk_pct
        self.max_open = max_open
        self.max_margin_pct = max_margin_pct

    def process(self, message_id: str, text: str, msg_date: str | None = None) -> ProcessResult:
        sig = parse(text)

        # 1) cisti chatter ne spremamo
        if sig.kind == SignalKind.UNKNOWN:
            return ProcessResult(message_id, sig.kind.value, sig.status.value, "IGNORED")

        # 2) idempotentnost
        if self.db.signal_exists(message_id):
            self.db.audit("duplicate_skipped", message_id, {"kind": sig.kind.value})
            return ProcessResult(message_id, sig.kind.value, sig.status.value, "SKIPPED_DUPLICATE")

        # 3) spremi signal (i ne-tradable, za Trade Manager / dataset)
        signal_id = self.db.insert_signal(message_id, sig, msg_date)
        self.db.audit("signal_stored", message_id, {"kind": sig.kind.value, "status": sig.status.value})

        if not sig.is_tradable:
            return ProcessResult(message_id, sig.kind.value, sig.status.value, "STORED")

        # 4) validacija simbola
        info = resolve_symbol(sig.pair)
        if not info.tradable:
            self.db.update_signal_status(signal_id, TradeStatus.SKIPPED_NO_SYMBOL, info.reason)
            self.db.audit("symbol_skipped", message_id, {"pair": sig.pair, "reason": info.reason})
            return ProcessResult(message_id, sig.kind.value, "SKIPPED_NO_SYMBOL",
                                 "SKIPPED_SYMBOL", note=info.reason)

        # 5) sizing + paper nalozi
        plan = plan_position(sig.entry, sig.stop, sig.leverage, self.capital, self.risk_pct)
        if plan is None:
            self.db.update_signal_status(signal_id, TradeStatus.NEEDS_REVIEW, "entry == stop")
            self.db.audit("sizing_failed", message_id, {"reason": "entry == stop"})
            return ProcessResult(message_id, sig.kind.value, "NEEDS_REVIEW", "STORED",
                                 note="entry == stop")

        # 6) limit istovremene izlozenosti (prije otvaranja pozicije)
        blocked = self._exposure_block(plan.margin)
        if blocked:
            self.db.update_signal_status(signal_id, TradeStatus.SKIPPED_EXPOSURE, blocked)
            self.db.audit("exposure_blocked", message_id, {"reason": blocked})
            return ProcessResult(message_id, sig.kind.value, "SKIPPED_EXPOSURE",
                                 "SKIPPED_EXPOSURE", note=blocked)

        pos_id = self.db.insert_position(signal_id, sig, plan, info.weex_symbol)
        for order in build_orders(sig, plan, info.weex_symbol, message_id):
            self.db.insert_order(signal_id, order)

        note = ""
        if plan.margin and plan.margin > self.db.balance():
            note = f"UPOZORENJE: margina {plan.margin:.2f} > stanje {self.db.balance():.2f}"
        self.db.audit("paper_position_planned", message_id,
                      {"symbol": info.weex_symbol, "qty": plan.quantity,
                       "margin": plan.margin, "note": note})
        return ProcessResult(message_id, sig.kind.value, sig.status.value,
                             "POSITION_PLANNED", pos_id, note)

    def _exposure_block(self, new_margin: float | None) -> str | None:
        """Vrati razlog blokade ili None ako je u redu."""
        if self.db.count_planned_positions() >= self.max_open:
            return f"max otvorenih pozicija ({self.max_open}) dosegnut"
        if new_margin is not None:
            limit = self.db.balance() * self.max_margin_pct
            if self.db.total_reserved_margin() + new_margin > limit:
                return (f"margina bi presla limit "
                        f"({self.max_margin_pct*100:.0f}% stanja = {limit:.2f} USDT)")
        return None
