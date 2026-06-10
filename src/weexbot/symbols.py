"""Mapiranje i validacija simbola za WEEX (kripto + TradFi/RWA).

Registar i mapiranja su u instruments.py. WEEX podrzava kripto, metale (XAUT/XAG),
naftu (XTI), tokenizovane dionice i RWA - sve uz USDT kolateral.

NAPOMENA: tocan WEEX REST simbol string potvrduje se u Fazi 3 uz API pristup.
"""
from __future__ import annotations

from dataclasses import dataclass

from .instruments import CRYPTO_BASES, NOT_LISTED, tradfi_symbol


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

    if base in NOT_LISTED or p in NOT_LISTED:
        return SymbolInfo(p, base, None, False, "Nije u podrzanoj WEEX listi")

    sym = tradfi_symbol(base)
    if sym:
        return SymbolInfo(p, base, sym, True, "OK (WEEX TradFi/RWA perpetual)")

    if base in CRYPTO_BASES:
        return SymbolInfo(p, base, base + "USDT", True, "OK (kripto perpetual)")

    if p.endswith("USDT"):
        return SymbolInfo(p, base, p, True, "OK (paper; WEEX format se potvrdjuje u Fazi 3)")

    return SymbolInfo(p, base, None, False, "Nepoznat format/simbol")
