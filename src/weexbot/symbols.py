"""Mapiranje i validacija simbola za WEEX (Faza 2, paper).

Metali (XAU/XAG/XAUT) -> nisu na WEEX kripto futures (vidi config.SKIP_SYMBOLS).
Sve *USDT kripto -> dozvoljeno u paper modu.

NAPOMENA: tocan WEEX REST simbol string (npr. "BTCUSDT" vs "cmt_btcusdt" vs
"BTC-USDT") potvrdjuje se u Fazi 3 kad dobijemo API pristup. Do tada koristimo
kanonski oblik (npr. "BTCUSDT") kao placeholder weex_symbol.
"""
from __future__ import annotations

from dataclasses import dataclass

from .config import SKIP_SYMBOLS

# Mjesto za buduce iznimke kad potvrdimo stvarni WEEX format (Faza 3).
SYMBOL_OVERRIDES: dict[str, str] = {}


@dataclass
class SymbolInfo:
    pair: str
    base: str
    weex_symbol: str | None
    tradable: bool
    reason: str


def resolve_symbol(pair: str) -> SymbolInfo:
    p = (pair or "").upper().strip()
    base = p[:-4] if p.endswith("USDT") else p

    if base in SKIP_SYMBOLS or p in SKIP_SYMBOLS:
        return SymbolInfo(p, base, None, False, "Metal/nije na WEEX kripto futures")
    if not p.endswith("USDT"):
        return SymbolInfo(p, base, None, False, "Nepoznat format para (ocekivano *USDT)")

    weex_symbol = SYMBOL_OVERRIDES.get(p, p)
    return SymbolInfo(p, base, weex_symbol, True,
                      "OK (paper; tocan WEEX format se potvrdjuje u Fazi 3)")
