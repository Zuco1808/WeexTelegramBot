"""Konfiguracija parsera i risk engine-a (Faza 1).

Sve dogovorene postavke na jednom mjestu. Kasnije ce ovo preci u config.yaml,
ali za Fazu 1 drzimo konstante u kodu radi jednostavnosti.
"""
import os


# --- WEEX API (Faza 3) - NIKAD ne hardkodirati kljuceve; citamo iz env-a ---
# Tocan base URL i format potpisa potvrdjuju se uz WEEX API dokumentaciju.
WEEX_BASE_URL: str = os.environ.get("WEEX_BASE_URL", "")


def weex_credentials() -> tuple[str | None, str | None]:
    """(api_key, api_secret) iz okruzenja; None ako nisu postavljeni."""
    return os.environ.get("WEEX_API_KEY"), os.environ.get("WEEX_API_SECRET")

# --- Risk / kapital (dogovoreno) ---
CAPITAL_USDT: float = 100.0       # pocetni simulacijski kapital
RISK_PCT_SCALP: float = 0.01      # 1% rizika po scalp signalu (Jeffrey + bot)
RISK_PCT_INTRADAY: float = 0.015  # 1.5% (Brandon zone - Faza 2)

# --- Leverage (dogovoreno: najniza vrijednost iz raspona, clampano na cap) ---
LEVERAGE_CAP: float = 10.0        # globalni hard-cap; nikad ne saljemo vise
DEFAULT_LEVERAGE_BOT: float = 5.0  # bot (Format C) ne salje leverage -> default

# --- Trade Manager lifecycle ---
# Pozicija neaktivna vise od ovoliko OBRADENIH poruka smatra se zatvorenom
# (heuristika; Brandon cesto ne posalje eksplicitni close). Smanjuje gomilanje
# "otvorenih" pozicija i posljedicno laznu dvosmislenost kod izmjena.
TM_STALE_TICKS: int = 40

# --- Limit istovremene izlozenosti (Faza 2, korak 2) ---
# Konzervativno: tretiramo sve PLANNED pozicije kao istovremene (jer paper ne
# simulira zatvaranje). Novi signal se odbija ako bi presao bilo koji limit.
MAX_OPEN_POSITIONS: int = 5                 # maks. broj planiranih pozicija
MAX_PORTFOLIO_MARGIN_PCT: float = 1.0       # maks. ukupna margina kao udio stanja (1.0 = 100%)

# --- Simboli koji NISU dostupni na WEEX kripto futures (dogovoreno: preskoci) ---
# Metali: zlato/srebro/Tether Gold. Parser ih i dalje parsira i logira,
# ali ih oznacava statusom SKIPPED_NO_SYMBOL i nikad ne salje nalog.
SKIP_SYMBOLS: frozenset[str] = frozenset({"XAU", "XAG", "XAUT", "XAGT"})

# TradFi/robe (dionice, indeksi, nafta...) - Brandon ih povremeno dijeli, ali
# NISU na WEEX kripto futures. Detektiramo ih da bismo ih JASNO oznacili kao
# preskocene (a ne kao "nepoznat ticker"). Prosiruj po potrebi.
NON_CRYPTO_SYMBOLS: frozenset[str] = frozenset({
    "PLTR", "OIL", "GOLD", "SILVER", "NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "META",
})

# --- Sto se smije auto-tradeati u Fazi 1 (dogovoreno) ---
# Samo precizni formati: Jeffrey scalp (A) i bot (C).
# Brandon zone (B), manual (D), update (E) -> NE trguju se automatski u Fazi 1.
