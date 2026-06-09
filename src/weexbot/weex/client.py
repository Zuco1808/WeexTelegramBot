"""Zajednicki tipovi i apstraktno sucelje WEEX klijenta.

Isti potpis koriste i paper i (buduci) stvarni REST klijent, pa se izvrsni
sloj ne mijenja kad predemo s papera na live.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

# Tipovi naloga uskladeni s paper_broker.PaperOrder.otype
ENTRY_LIMIT = "ENTRY_LIMIT"
STOP_LOSS = "STOP_LOSS"
TAKE_PROFIT = "TAKE_PROFIT"
MARKET = "MARKET"


@dataclass
class OrderRequest:
    symbol: str
    side: str                       # BUY | SELL
    otype: str                      # ENTRY_LIMIT | STOP_LOSS | TAKE_PROFIT | MARKET
    quantity: float
    price: float | None = None      # None za MARKET
    reduce_only: bool = False
    client_order_id: str | None = None
    leverage: float | None = None


@dataclass
class OrderResult:
    client_order_id: str
    status: str                     # WORKING | FILLED | CANCELLED | REJECTED
    filled_price: float | None = None
    message: str = ""


@dataclass
class PaperPosition:
    symbol: str
    side: str                       # LONG | SHORT
    quantity: float
    entry_price: float
    leverage: float | None = None
    realized_pnl: float = 0.0


class WeexClient(ABC):
    """Apstraktno sucelje; paper i REST implementacija ga dijele."""

    @abstractmethod
    def set_leverage(self, symbol: str, leverage: float,
                     margin_mode: str = "isolated") -> None: ...

    @abstractmethod
    def place_order(self, req: OrderRequest) -> OrderResult: ...

    @abstractmethod
    def cancel_order(self, client_order_id: str) -> OrderResult: ...

    @abstractmethod
    def open_orders(self, symbol: str | None = None) -> list[OrderResult]: ...

    @abstractmethod
    def positions(self) -> list[PaperPosition]: ...

    @abstractmethod
    def mark_price(self, symbol: str) -> float | None: ...
