"""Reconciler (Faza 3.3) - zatvoreni nalozi s burze -> trades ledger.

Cita order history s WEEX-a, prepoznaje FILLED CLOSE naloge (close_long/close_short)
i biljezi realizirani PnL (totalProfits) u trades tablicu. Dedup po order_id (ext_id),
pa visekratno pokretanje ne duplicira. Time dashboard prikazuje STVARNI PnL.

Klijent mora imati order_history(symbol) -> dict (WEEX odgovor).
"""
from __future__ import annotations

from datetime import datetime, timezone


def _rows(resp) -> list[dict]:
    if isinstance(resp, list):
        return [r for r in resp if isinstance(r, dict)]
    if isinstance(resp, dict):
        d = resp.get("data", resp)
        if isinstance(d, dict):
            d = d.get("list", [])
        return [r for r in d if isinstance(r, dict)] if isinstance(d, list) else []
    return []


def _f(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _iso(ms) -> str | None:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None


class Reconciler:
    def __init__(self, client, db, source: str = "live"):
        self.client = client
        self.db = db
        self.source = source

    def reconcile(self, symbols: list[str]) -> int:
        """Vrati broj NOVIH zabiljezenih zatvorenih trejdova."""
        new = 0
        for sym in symbols:
            for o in _rows(self.client.order_history(sym)):
                typ = str(o.get("type", "")).lower()
                if "close" not in typ:                       # samo zatvarajuci nalozi
                    continue
                filled = _f(o.get("filled_qty") or o.get("filledQty"))
                if filled <= 0:                               # samo izvrseni
                    continue
                ext = str(o.get("order_id") or o.get("orderId") or "")
                if not ext or self.db.trade_exists(ext):
                    continue
                pnl = _f(o.get("totalProfits") or o.get("profit"))
                side = "LONG" if "long" in typ else "SHORT"
                ts = o.get("createTime") or o.get("cTime") or o.get("uTime")
                exit_price = _f(o.get("price_avg") or o.get("priceAvg")) or None
                self.db.record_trade(
                    symbol=sym, side=side, quantity=filled, entry_price=None,
                    exit_price=exit_price, pnl=pnl, closed_at=_iso(ts),
                    source=self.source, ext_id=ext)
                new += 1
        return new
