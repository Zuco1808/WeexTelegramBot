"""SignalRouter (Faza 3.6) - usmjeravanje dolaznih poruka (cista, testabilna logika).

Telethon je samo transport (run_telegram.py); ovdje je sva logika:
  - dedup po message_id (signals tablica)
  - parse -> ruta:
      * TRADABLE (Jeffrey A / bot C) -> LiveExecutor.plan; semi-auto (NOTIFY) ili --auto (PLACE)
      * ostalo (Brandon D / update E) -> TradeManager (korelacija)
      * UNKNOWN chatter -> ignorira

Default je SEMI-AUTO: ne salje nalog sam, nego javi plan (on_plan callback) i
zabiljezi ga. 'auto' mod salje samo ako je entry u +-1% bandu.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from .models import SignalKind
from .parser import parse


@dataclass
class RouterResult:
    message_id: str
    action: str               # DUPLICATE|IGNORED|NOTIFY|PLACED|PLAN_REJECTED|TRACKED|TRADABLE_NOEXEC
    detail: dict


class SignalRouter:
    def __init__(self, db, trade_manager, executor=None, mode: str = "notify", on_plan=None):
        self.db = db
        self.tm = trade_manager
        self.executor = executor          # LiveExecutor ili None
        self.mode = mode                  # "notify" (semi-auto) | "auto"
        self.on_plan = on_plan            # callback(message_id, signal, plan) za obavijest

    def handle(self, message_id: str, text: str, msg_date: str | None = None) -> RouterResult:
        if self.db.signal_exists(message_id):
            return RouterResult(message_id, "DUPLICATE", {})

        sig = parse(text)
        if sig.kind == SignalKind.UNKNOWN:
            return RouterResult(message_id, "IGNORED", {"kind": "UNKNOWN"})

        self.db.insert_signal(message_id, sig, msg_date)

        if sig.is_tradable:
            return self._handle_tradable(message_id, sig)

        # Brandon D / update E -> Trade Manager (korelacija/pracenje)
        actions = self.tm.process(message_id, text)
        return RouterResult(message_id, "TRACKED",
                            {"kind": sig.kind.value, "tm": [a.kind for a in actions]})

    def _handle_tradable(self, message_id: str, sig) -> RouterResult:
        if self.executor is None:
            self.db.audit("tradable_no_executor", message_id, {"pair": sig.pair})
            return RouterResult(message_id, "TRADABLE_NOEXEC", {"pair": sig.pair})

        plan = self.executor.plan(sig)
        if not plan.ok:
            self.db.audit("plan_rejected", message_id, {"reason": plan.reason})
            return RouterResult(message_id, "PLAN_REJECTED", {"reason": plan.reason})

        if self.on_plan:
            try:
                self.on_plan(message_id, sig, plan)
            except Exception:             # obavijest ne smije srusiti ingest
                pass

        if self.mode == "auto" and plan.in_band:
            res = self.executor.place(plan, client_order_id=f"sig{int(time.time())}")
            self.db.audit("auto_placed", message_id,
                          {"symbol": plan.symbol, "qty": plan.quantity})
            return RouterResult(message_id, "PLACED",
                                {"symbol": plan.symbol, "result": getattr(res, "status", "")})

        # semi-auto: samo javi plan, ne salji
        self.db.audit("plan_notify", message_id,
                      {"symbol": plan.symbol, "in_band": plan.in_band})
        return RouterResult(message_id, "NOTIFY",
                            {"symbol": plan.symbol, "side": plan.side,
                             "qty": plan.quantity, "in_band": plan.in_band})
