"""WEEX podrzani instrumenti - kripto + TradFi/RWA (USDT-margined perpetuals).

Izvor: sluzbena WEEX TradFi/RWA lista (trgovanje uz USDT kolateral).
Za FUTURES koristimo USDT perpetual (NE 'ON' spot/RWA varijantu).

Mapiranja (potvrdeno od korisnika):
  - GOLD/XAUT/XAU -> XAUTUSDT (primarno; PAXG kao alternativa)
  - SILVER/XAG    -> XAGUSDT
  - OIL/WTI       -> XTIUSDT  (WEEX WTI ugovor je lansiran kao XTI)
  - 'ON' sufiks   -> odbaci, koristi USDT perpetual (GOOGLON -> GOOGLUSDT)
"""
from __future__ import annotations

# Kripto bazni simboli (iz kanala + cesti majori). Metali su izdvojeni u TradFi.
CRYPTO_BASES: frozenset[str] = frozenset({
    "BTC", "ETH", "BNB", "XRP", "SOL", "ADA", "AVAX", "LINK", "TON", "TRX", "DOGE",
    "ASTER", "PUMP", "FF", "FARTCOIN", "ZEC", "EGLD", "ETC", "LTC", "ATOM", "HBAR",
    "XMR", "DOT", "NEAR", "APT", "ARB", "OP", "INJ", "SUI", "SEI", "TIA", "RUNE",
    "AAVE", "UNI", "FIL",
})

# Prijateljsko ime (kako Brandon pise) -> WEEX USDT perpetual simbol.
TRADFI_REGISTRY: dict[str, str] = {
    # --- plemeniti metali ---
    "GOLD": "XAUTUSDT", "XAUT": "XAUTUSDT", "XAU": "XAUTUSDT", "PAXG": "PAXGUSDT",
    "SILVER": "XAGUSDT", "XAG": "XAGUSDT",
    # --- energenti ---
    "OIL": "XTIUSDT", "WTI": "XTIUSDT", "XTI": "XTIUSDT", "BRN": "BRNUSDT", "NG": "NGUSDT",
    # --- tokenizovane americke dionice (USDT perpetual, bez 'ON') ---
    "MSFT": "MSFTUSDT", "AAPL": "AAPLUSDT", "GOOGL": "GOOGLUSDT", "COIN": "COINUSDT",
    "SPCX": "SPCXUSDT", "LMT": "LMTUSDT", "PAYP": "PAYPUSDT", "AMD": "AMDUSDT",
    "ARM": "ARMUSDT", "COHR": "COHRUSDT",
    "GOOGLON": "GOOGLUSDT", "COINON": "COINUSDT",
    # --- RWA tokenizovane dionice ('ON' spot -> USDT perpetual) ---
    "INTCON": "INTCUSDT", "MUON": "MUUSDT", "SNDKON": "SNDKUSDT", "WDCON": "WDCUSDT",
    "STXON": "STXUSDT", "CRCLON": "CRCLUSDT", "BMNRON": "BMNRUSDT",
    # --- forex / indeksi (priblizni simboli; tocan string potvrda u Fazi 3) ---
    "EUR": "EURUSDT", "GBP": "GBPUSDT", "SPX": "SPXUSDT", "NDX": "NDXUSDT",
    "NAS100": "NAS100USDT",
}

# Eksplicitno NEpodrzano na WEEX (dionice kojih nema u sluzbenoj listi).
NOT_LISTED: frozenset[str] = frozenset({"PLTR", "NVDA", "TSLA", "AMZN", "META"})

# Sve TradFi baze koje uopce prepoznajemo (za detekciju para u manual_parseru).
TRADFI_BASES: frozenset[str] = frozenset(TRADFI_REGISTRY) | NOT_LISTED


def tradfi_symbol(base: str) -> str | None:
    """WEEX perpetual za TradFi prijateljsko ime, ili None ako nije TradFi."""
    b = (base or "").upper()
    if b in TRADFI_REGISTRY:
        return TRADFI_REGISTRY[b]
    # generic 'ON' sufiks (RWA spot) -> USDT perpetual; ne dira kratke kripto (TON)
    if b.endswith("ON") and len(b) > 4 and b[:-2].isalpha():
        return b[:-2] + "USDT"
    return None
