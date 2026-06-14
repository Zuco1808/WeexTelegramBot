"""Sigurnosni sloj (Faza 3.7): kill-switch, dnevni stop-loss, limit izlozenosti.

SafetyGate.check() vraca (ok, reason); izvrsitelj/router ga konzultiraju PRIJE
slanja naloga. Kill-switch je datoteka (lako ručno ukljuciti). Dnevni gubitak
se racuna iz trades ledgera (realizirani PnL danas).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone

from .config import DAILY_LOSS_LIMIT_USDT, MAX_CONCURRENT_POSITIONS
from .reports import trades_from_rows


# --- kill-switch (datoteka) ------------------------------------------------- #
def kill_active(path: str) -> bool:
    return os.path.exists(path)


def engage_kill(path: str, reason: str = "") -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()}  {reason}\n")


def clear_kill(path: str) -> bool:
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


# --- dnevni realizirani PnL ------------------------------------------------- #
def daily_realized_pnl(db, source: str | None = "live", day=None) -> float:
    day = day or datetime.now(timezone.utc).date()
    total = 0.0
    for t in trades_from_rows(db.trades()):
        if source and t.source != source:
            continue
        if t.closed_at.date() == day:
            total += t.pnl
    return total


# --- gate ------------------------------------------------------------------- #
@dataclass
class GateResult:
    ok: bool
    reason: str


class SafetyGate:
    def __init__(self, db, kill_path: str,
                 max_positions: int = MAX_CONCURRENT_POSITIONS,
                 daily_loss_limit: float | None = DAILY_LOSS_LIMIT_USDT,
                 count_open=None):
        self.db = db
        self.kill_path = kill_path
        self.max_positions = max_positions
        self.daily_loss_limit = daily_loss_limit
        self.count_open = count_open          # callable -> broj otvorenih pozicija

    def check(self) -> GateResult:
        if kill_active(self.kill_path):
            return GateResult(False, "kill-switch aktivan")
        if self.daily_loss_limit is not None:
            pnl = daily_realized_pnl(self.db)
            if pnl <= -abs(self.daily_loss_limit):
                return GateResult(False, f"dnevni gubitak {pnl:.2f} <= -{self.daily_loss_limit:g} USDT")
        if self.count_open is not None and self.max_positions is not None:
            n = self.count_open()
            if n >= self.max_positions:
                return GateResult(False, f"max istovremenih pozicija ({self.max_positions}) dosegnut")
        return GateResult(True, "OK")
