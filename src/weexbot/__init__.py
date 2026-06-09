"""weexbot - parser trading signala iz Telegrama (Faza 1).

Javni API:
    parse(raw_text) -> Signal
    normalize(raw_text) -> str
    classify(text) -> SignalKind
"""
from .models import Signal, TakeProfit, Side, SignalKind, TradeStatus
from .normalize import normalize
from .classify import classify
from .parser import parse
from .db import Database
from .pipeline import Pipeline, ProcessResult
from .symbols import resolve_symbol
from .trade_manager import TradeManager, TradeAction

__all__ = [
    "parse",
    "normalize",
    "classify",
    "Signal",
    "TakeProfit",
    "Side",
    "SignalKind",
    "TradeStatus",
    "Database",
    "Pipeline",
    "ProcessResult",
    "resolve_symbol",
    "TradeManager",
    "TradeAction",
]
