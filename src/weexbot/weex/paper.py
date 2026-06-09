"""PaperWeexClient - lokalna simulacija burze s fill-ovima na temelju cijene.

Bez mreze i bez kljuceva. `feed_price(symbol, price)` gura cijenu i izvrsava
naloge koji su time okinuti:
  - ENTRY_LIMIT: BUY puni kad cijena <= limit; SELL kad cijena >= limit
  - TAKE_PROFIT: isto kao limit (reduce-only)
  - STOP_LOSS:   BUY-stop okida kad cijena >= stop; SELL-stop kad cijena <= stop

Kad se pozicija u potpunosti zatvori, preostali reduce-only nalozi za taj simbol
se otkazuju (OCO ponasanje SL/TP para).
"""
from __future__ import annotations

from .client import (
    ENTRY_LIMIT,
    STOP_LOSS,
    TAKE_PROFIT,
    OrderRequest,
    OrderResult,
    PaperPosition,
    WeexClient,
)


def _triggered(otype: str, side: str, limit: float, price: float) -> bool:
    if otype in (ENTRY_LIMIT, TAKE_PROFIT):
        return price <= limit if side == "BUY" else price >= limit
    if otype == STOP_LOSS:
        return price >= limit if side == "BUY" else price <= limit
    return False


class PaperWeexClient(WeexClient):
    def __init__(self, balance: float = 100.0):
        self.balance = balance
        self.leverage: dict[str, float] = {}
        self.margin_mode: dict[str, str] = {}
        self._orders: dict[str, dict] = {}        # coid -> {"req":.., "status":..,"filled":..}
        self._positions: dict[str, PaperPosition] = {}
        self._last: dict[str, float] = {}
        self._seq = 0

    # --- WeexClient API --------------------------------------------------- #
    def set_leverage(self, symbol: str, leverage: float,
                     margin_mode: str = "isolated") -> None:
        self.leverage[symbol] = leverage
        self.margin_mode[symbol] = margin_mode

    def place_order(self, req: OrderRequest) -> OrderResult:
        self._seq += 1
        coid = req.client_order_id or f"paper-{self._seq}"
        if req.leverage is not None:
            self.set_leverage(req.symbol, req.leverage)
        self._orders[coid] = {"req": req, "status": "WORKING", "filled": None}

        # MARKET ili limit koji je vec "u novcu" -> odmah pokusaj fill na zadnjoj cijeni
        last = self._last.get(req.symbol)
        if req.otype == "MARKET" and last is not None:
            self._fill(coid, last)
        elif last is not None and req.price is not None and \
                _triggered(req.otype, req.side, req.price, last):
            self._fill(coid, req.price)
        o = self._orders[coid]
        return OrderResult(coid, o["status"], o["filled"])

    def cancel_order(self, client_order_id: str) -> OrderResult:
        o = self._orders.get(client_order_id)
        if o is None:
            return OrderResult(client_order_id, "REJECTED", message="ne postoji")
        if o["status"] == "WORKING":
            o["status"] = "CANCELLED"
        return OrderResult(client_order_id, o["status"])

    def open_orders(self, symbol: str | None = None) -> list[OrderResult]:
        out = []
        for coid, o in self._orders.items():
            if o["status"] != "WORKING":
                continue
            if symbol and o["req"].symbol != symbol:
                continue
            out.append(OrderResult(coid, o["status"], o["filled"]))
        return out

    def positions(self) -> list[PaperPosition]:
        return list(self._positions.values())

    def mark_price(self, symbol: str) -> float | None:
        return self._last.get(symbol)

    # --- simulacija cijene ------------------------------------------------ #
    def feed_price(self, symbol: str, price: float) -> list[OrderResult]:
        """Gurni cijenu; vrati listu naloga koji su upravo izvrseni."""
        self._last[symbol] = price
        filled: list[OrderResult] = []
        for coid, o in list(self._orders.items()):
            if o["status"] != "WORKING" or o["req"].symbol != symbol:
                continue
            req = o["req"]
            if req.price is not None and _triggered(req.otype, req.side, req.price, price):
                self._fill(coid, req.price)
                filled.append(OrderResult(coid, "FILLED", req.price))
        return filled

    # --- interno ---------------------------------------------------------- #
    def _fill(self, coid: str, fill_price: float) -> None:
        o = self._orders[coid]
        req: OrderRequest = o["req"]
        o["status"] = "FILLED"
        o["filled"] = fill_price

        if req.reduce_only:
            self._reduce(req, fill_price)
        else:
            self._open(req, fill_price)

    def _open(self, req: OrderRequest, price: float) -> None:
        side = "LONG" if req.side == "BUY" else "SHORT"
        pos = self._positions.get(req.symbol)
        if pos is None:
            self._positions[req.symbol] = PaperPosition(
                symbol=req.symbol, side=side, quantity=req.quantity,
                entry_price=price, leverage=self.leverage.get(req.symbol),
            )
            return
        # isti smjer -> prosjeci ulaz; suprotni -> (pojednostavljeno) povecaj/umanji
        if pos.side == side:
            total = pos.quantity + req.quantity
            pos.entry_price = (pos.entry_price * pos.quantity + price * req.quantity) / total
            pos.quantity = total
        else:
            pos.quantity -= req.quantity
            if pos.quantity <= 0:
                del self._positions[req.symbol]

    def _reduce(self, req: OrderRequest, price: float) -> None:
        pos = self._positions.get(req.symbol)
        if pos is None:
            return
        qty = min(req.quantity, pos.quantity)
        sign = 1 if pos.side == "LONG" else -1
        pnl = qty * (price - pos.entry_price) * sign
        self.balance += pnl
        pos.realized_pnl += pnl
        pos.quantity -= qty
        if pos.quantity <= 1e-12:
            del self._positions[req.symbol]
            self._cancel_reduce_only(req.symbol)

    def _cancel_reduce_only(self, symbol: str) -> None:
        for o in self._orders.values():
            if (o["status"] == "WORKING" and o["req"].symbol == symbol
                    and o["req"].reduce_only):
                o["status"] = "CANCELLED"
