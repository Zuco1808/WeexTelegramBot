"""Sloj 2: klasifikacija - koji je format poruke?

Redoslijed provjere je vazan (od najspecificnijeg prema najopcenitijem):
    INFO (legenda) -> A (Jeffrey) -> C (bot) -> B (zona) -> D (manual) -> E (update)
Ako nista ne odgovara -> UNKNOWN (najcesce cisti komentar/chatter).
"""
import re

from .models import SignalKind

# Legenda/pravila: dugacka poruka s tipicnim uvodnim frazama.
_RE_INFO = re.compile(r"(how to use|welcome|general rules|no kyc|two analysts)", re.I)

# A: pocinje s $TICKERUSDT long/short entry -
_RE_A = re.compile(r"^\$[A-Z0-9]+USDT\s*(long|short)\s*entry\s*-", re.I)

# C: PARUSDT <timeframe> Short/Long Price:
_RE_C = re.compile(r"[A-Z0-9]+USDT\s*\d+\s*[mhd]\s*(long|short)\s*price\s*:", re.I)

# B: PAIR/SIDE ... Entry point:
_RE_B = re.compile(r"[A-Z]{2,}\s*/\s*(long|short).*entry\s*point\s*:", re.I)

# D: rucni format s eksplicitnim kljucnim rijecima
_RE_D = re.compile(r"(stop\s*-?\s*loss\s*:|stoploss\s*:|target\s*:|entry\s*levels?\s*:|entry\s*:)", re.I)

# E: izmjena postojece pozicije / upravljanje.
# Bez globalnog \b...\b jer se TP cesto lijepi uz znamenku ("1TP") ili %,
# pa svaku alternativu sidrimo zasebno gdje ima smisla.
_RE_E = re.compile(
    r"(?:\bsl\b|\bbreakeven\b|move\s+(?:the\s+)?stop|mov\w*\s+sl|tp\d?\b|fix\s*\d)",
    re.I,
)


def classify(text: str) -> SignalKind:
    """Ocekuje vec normaliziran tekst (vidi normalize.normalize)."""
    t = (text or "").strip()
    if not t:
        return SignalKind.UNKNOWN
    if len(t) > 300 and _RE_INFO.search(t):
        return SignalKind.INFO
    if _RE_A.search(t):
        return SignalKind.JEFFREY
    if _RE_C.search(t):
        return SignalKind.BOT
    if _RE_B.search(t):
        return SignalKind.ZONE
    if _RE_D.search(t):
        return SignalKind.MANUAL
    if _RE_E.search(t):
        return SignalKind.UPDATE
    return SignalKind.UNKNOWN
