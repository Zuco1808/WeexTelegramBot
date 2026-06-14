"""LiveExecutor (Faza 3.5) - pretvara Signal u WEEX nalog, semi-auto.

- stvarni balans za sizing (account_balance)
- per-simbol spec (zaokruzivanje qty/cijene, min veličina) iz symbol_spec
- rizik RISK_PCT_LIVE; leverage min(signal, cap), isolated
- entry limit + preset SL/TP zakaceni na entry nalog
- band: limit dozvoljen samo unutar +-limitPriceRatio od cijene; izvan -> PENDING

LiveExecutor.plan() je read-only (racuna i validira). place() salje nalog.
Klijent mora imati: mark_price, account_balance, symbol_spec, set_leverage, place_order.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .config import LEVERAGE_CAP, MARGIN_MODE, RISK_PCT_LIVE
from .models import Side, Signal
from .symbols import resolve_symbol
from .weex.client import ENTRY_LIMIT, OrderRequest


def _floor(x: float, precision: int) -> float:
    f = 10 ** precision
    return math.floor(x * f) / f


@dataclass
class OrderPlan:
    ok: bool
    reason: str
    symbol: str | None = None            # WEEX simbol (npr. BTCUSDT)
    side: str | None = None              # BUY / SELL
    quantity: float = 0.0
    entry: float | None = None
    stop: float | None = None
    take_profit: float | None = None
    leverage: float = 0.0
    notional: float = 0.0
    margin: float = 0.0
    risk_usdt: float = 0.0
    mark: float | None = None
    in_band: bool = False                # je li entry unutar dozvoljenog +-ratio


class LiveExecutor:
    def __init__(self, client, risk_pct: float = RISK_PCT_LIVE,
                 leverage_cap: float = LEVERAGE_CAP, margin_mode: str = MARGIN_MODE):
        self.client = client
        self.risk_pct = risk_pct
        self.leverage_cap = leverage_cap
        self.margin_mode = margin_mode

    # ------------------------------------------------------------------ #
    def plan(self, signal: Signal) -> OrderPlan:
        if not signal.is_tradable:
            return OrderPlan(False, f"signal nije TRADABLE ({signal.status.value})")
        info = resolve_symbol(signal.pair or "")
        if not info.tradable:
            return OrderPlan(False, f"simbol nije na WEEX: {info.reason}")

        entry = signal.entry
        if entry is None and signal.entry_zone:
            entry = (signal.entry_zone[0] + signal.entry_zone[1]) / 2
        if entry is None or signal.stop is None:
            return OrderPlan(False, "nedostaje entry ili stop")
        dist = abs(entry - signal.stop)
        if dist == 0:
            return OrderPlan(False, "entry == stop")

        spec = self.client.symbol_spec(info.weex_symbol)
        mark = self.client.mark_price(info.weex_symbol)
        balance = self.client.account_balance()
        if not mark or balance <= 0:
            return OrderPlan(False, "nema cijene ili balansa")

        pp, qp = spec["pricePrecision"], spec["quantityPrecision"]
        risk_usdt = balance * self.risk_pct
        qty = _floor(risk_usdt / dist, qp)
        if qty < spec["minOrderSize"]:
            return OrderPlan(False,
                             f"qty {qty} < minOrderSize {spec['minOrderSize']} "
                             f"(stop preuzak za 2% rizika na {balance:.2f} USDT)")

        side = Side(signal.side).value if isinstance(signal.side, str) else signal.side.value
        is_long = side == "LONG"
        order_side = "BUY" if is_long else "SELL"
        lev = min(signal.leverage or self.leverage_cap, self.leverage_cap)

        entry_r = round(entry, pp)
        stop_r = round(signal.stop, pp)
        tp = signal.take_profits[0].price if signal.take_profits else None
        tp_r = round(tp, pp) if tp is not None else None

        ratio = spec["buyLimitPriceRatio"] if is_long else spec["sellLimitPriceRatio"]
        in_band = abs(entry_r - mark) / mark <= ratio
        notional = qty * entry_r
        margin = notional / lev if lev else 0.0

        return OrderPlan(
            ok=True, reason="OK", symbol=info.weex_symbol, side=order_side,
            quantity=qty, entry=entry_r, stop=stop_r, take_profit=tp_r,
            leverage=lev, notional=notional, margin=margin, risk_usdt=risk_usdt,
            mark=mark, in_band=in_band,
        )

    # ------------------------------------------------------------------ #
    def place(self, plan: OrderPlan, client_order_id: str | None = None):
        """Postavi leverage pa plasiraj entry limit + preset SL/TP. (PISE na WEEX)"""
        if not plan.ok:
            raise ValueError(f"plan nije valjan: {plan.reason}")
        self.client.set_leverage(plan.symbol, plan.leverage, self.margin_mode)
        req = OrderRequest(
            symbol=plan.symbol, side=plan.side, otype=ENTRY_LIMIT,
            quantity=plan.quantity, price=plan.entry,
            preset_sl=plan.stop, preset_tp=plan.take_profit,
            client_order_id=client_order_id, leverage=plan.leverage,
        )
        return self.client.place_order(req)
