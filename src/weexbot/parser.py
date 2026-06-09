"""Sloj 3: glavni parser - normalizira, klasificira i rutira na ekstraktore.

Javna funkcija: parse(raw_text) -> Signal

Faza 1 trguje SAMO Format A (Jeffrey) i Format C (bot) -> status TRADABLE.
Format B (zona) se parsira "best-effort" ali NIKAD ne dobiva TRADABLE u Fazi 1.
Format D/E/INFO/UNKNOWN se samo klasificiraju (Trade Manager je Faza 6).
"""
import re

from .classify import classify
from .config import (
    DEFAULT_LEVERAGE_BOT,
    LEVERAGE_CAP,
    SKIP_SYMBOLS,
)
from .models import Side, Signal, SignalKind, TakeProfit, TradeStatus
from .normalize import normalize

# --- Format A: $ETHUSDTlongentry - 2739.56; stop - 2632.84take - 2825.47; leverage - x11
_RE_A = re.compile(
    r"\$(?P<pair>[A-Z0-9]+USDT)\s*(?P<side>long|short)\s*"
    r"entry\s*-\s*(?P<entry>[\d.]+)\s*;?\s*"
    r"stop\s*-\s*(?P<stop>[\d.]+)\s*"
    r"take\s*-\s*(?P<take>[\d.]+)\s*;?\s*"
    r"leverage\s*-\s*x?(?P<lev>[\d.]+)",
    re.I,
)

# --- Format C: ETHUSDT 15mShortPrice: 2060.5TP2: 1932.92SL: 2195.0
_RE_C = re.compile(
    r"(?P<pair>[A-Z0-9]+USDT)\s*(?P<tf>\d+\s*[mhd])\s*(?P<side>long|short)\s*"
    r"price\s*:\s*(?P<entry>[\d.]+)\s*"
    r"tp(?P<tpidx>\d+)\s*:\s*(?P<tp>[\d.]+)\s*"
    r"sl\s*:\s*(?P<sl>[\d.]+)",
    re.I,
)

# --- Format B header: XAUT/SHORT 15-40Entry point: 4750-4850
_RE_B_HEAD = re.compile(
    r"(?P<pair>[A-Z]{2,})\s*/\s*(?P<side>long|short)\s*"
    r"x?(?P<levlo>[\d.]+)\s*-\s*(?P<levhi>[\d.]+)\s*"
    r"entry\s*point\s*:\s*(?P<elo>[\d.]+)\s*-\s*(?P<ehi>[\d.]+)",
    re.I,
)
# TP blok: "<cijena> / fix NN%"  ili  "<cijena> / move stop to breakeven"
_RE_B_TP = re.compile(
    r"(?P<tp>[\d.]+)\s*/\s*(?P<action>(?:we\s+)?fix\s*\d+\s*%|move\s+(?:the\s+)?stop[^0-9]*)",
    re.I,
)
_RE_B_SL = re.compile(r"sl\s*=\s*(?P<sl>[\d.]+)", re.I)


def parse(raw: str) -> Signal:
    """Glavni ulaz: sirovi tekst poruke -> normalizirani Signal."""
    text = normalize(raw)
    kind = classify(text)

    if kind == SignalKind.JEFFREY:
        return _parse_a(text, raw)
    if kind == SignalKind.BOT:
        return _parse_c(text, raw)
    if kind == SignalKind.ZONE:
        return _parse_b(text, raw)
    if kind == SignalKind.MANUAL:
        return Signal(
            kind=kind, raw_text=raw, status=TradeStatus.NEEDS_REVIEW, confidence=0.3,
            notes=["Manual format (D) - ne trguje se u Fazi 1; rucni pregled."],
        )
    if kind == SignalKind.UPDATE:
        return _parse_update(text, raw)
    if kind == SignalKind.INFO:
        return Signal(
            kind=kind, raw_text=raw, status=TradeStatus.INFO, confidence=1.0,
            notes=["Legenda/info poruka - ignorirati."],
        )
    return Signal(kind=SignalKind.UNKNOWN, raw_text=raw, status=TradeStatus.NEEDS_REVIEW,
                  confidence=0.0, notes=["Nije prepoznat format (vjerojatno komentar)."])


# --------------------------------------------------------------------------- #
# Ekstraktori po formatu
# --------------------------------------------------------------------------- #
def _side(token: str) -> Side:
    return Side.LONG if token.lower() == "long" else Side.SHORT


def _clamp_leverage(value: float, sig: Signal) -> float:
    if value > LEVERAGE_CAP:
        sig.notes.append(f"Leverage x{value:g} clampan na cap x{LEVERAGE_CAP:g}.")
        return LEVERAGE_CAP
    return value


def _parse_a(text: str, raw: str) -> Signal:
    m = _RE_A.search(text)
    if not m:
        return Signal(SignalKind.JEFFREY, raw, status=TradeStatus.NEEDS_REVIEW, confidence=0.4,
                      notes=["Klasificiran kao Jeffrey, ali ekstrakcija polja nije uspjela."])
    sig = Signal(
        kind=SignalKind.JEFFREY, raw_text=raw,
        pair=m["pair"].upper(), side=_side(m["side"]),
        entry=float(m["entry"]), stop=float(m["stop"]),
        take_profits=[TakeProfit(price=float(m["take"]), fraction=1.0)],
        status=TradeStatus.TRADABLE, confidence=0.97,
    )
    sig.leverage = _clamp_leverage(float(m["lev"]), sig)
    _validate_direction(sig)
    _check_skip_symbol(sig)
    return sig


def _parse_c(text: str, raw: str) -> Signal:
    m = _RE_C.search(text)
    if not m:
        return Signal(SignalKind.BOT, raw, status=TradeStatus.NEEDS_REVIEW, confidence=0.4,
                      notes=["Klasificiran kao bot, ali ekstrakcija polja nije uspjela."])
    sig = Signal(
        kind=SignalKind.BOT, raw_text=raw,
        pair=m["pair"].upper(), side=_side(m["side"]),
        entry=float(m["entry"]), stop=float(m["sl"]),
        take_profits=[TakeProfit(price=float(m["tp"]), fraction=None)],
        timeframe=m["tf"].replace(" ", "").lower(),
        leverage=DEFAULT_LEVERAGE_BOT,
        status=TradeStatus.TRADABLE, confidence=0.95,
        notes=[f"Bot signal nema leverage; koristim default x{DEFAULT_LEVERAGE_BOT:g}.",
               f"Prisutan samo TP{m['tpidx']} u poruci."],
    )
    _validate_direction(sig)
    _check_skip_symbol(sig)
    return sig


def _parse_b(text: str, raw: str) -> Signal:
    h = _RE_B_HEAD.search(text)
    if not h:
        return Signal(SignalKind.ZONE, raw, status=TradeStatus.NEEDS_REVIEW, confidence=0.3,
                      notes=["Klasificiran kao zona, ali header nije parsiran (vjerojatno skracena poruka)."])
    pair = h["pair"].upper()
    tps: list[TakeProfit] = []
    for tm in _RE_B_TP.finditer(text[h.end():]):
        action = tm["action"].lower()
        frac = None
        fm = re.search(r"fix\s*(\d+)", action)
        if fm:
            frac = int(fm.group(1)) / 100.0
        move = "breakeven" if "breakeven" in action else ("tp2" if "2nd" in action else None)
        tps.append(TakeProfit(price=float(tm["tp"]), fraction=frac, move_sl_after=move))

    sl_m = _RE_B_SL.search(text)
    lev_lo, lev_hi = float(h["levlo"]), float(h["levhi"])

    sig = Signal(
        kind=SignalKind.ZONE, raw_text=raw,
        pair=pair, side=_side(h["side"]),
        entry_zone=(float(h["elo"]), float(h["ehi"])),
        stop=float(sl_m["sl"]) if sl_m else None,
        take_profits=tps,
        leverage_range=(lev_lo, lev_hi),
        confidence=0.8 if sl_m else 0.5,
        notes=["Brandon zona (B) - parsirano, ali se NE trguje u Fazi 1."],
    )
    sig.leverage = _clamp_leverage(lev_lo, sig)
    # Status: metal -> SKIPPED; inace izvan opsega Faze 1.
    if pair in SKIP_SYMBOLS:
        sig.status = TradeStatus.SKIPPED_NO_SYMBOL
        sig.notes.append(f"{pair} nije na WEEX kripto futures -> SKIPPED_NO_SYMBOL.")
    else:
        sig.status = TradeStatus.NOT_TRADED_PHASE1
    return sig


def _parse_update(text: str, raw: str) -> Signal:
    low = text.lower()
    if re.search(r"move\s+sl|moving\s+sl|now it will be at", low):
        sub = "MOVE_SL"
    elif "breakeven" in low:
        sub = "SL_BREAKEVEN"
    elif re.search(r"fix\s*\d", low):
        sub = "PARTIAL_FIX"
    elif low.strip() == "sl":
        sub = "SL_HIT"
    elif re.search(r"\btp\d?\b", low):
        sub = "TP_INFO"
    else:
        sub = "COMMENT"

    notes = [f"Update poruka ({sub}) - veze se na otvorenu poziciju "
             f"(Trade Manager, Faza 6). U Fazi 1: u nedoumici PITAJ, ne izvrsavaj."]
    num = re.search(r"(\d[\d.]*)", text)
    if sub == "MOVE_SL" and num:
        notes.append(f"Detektirana ciljna SL vrijednost: {num.group(1)}")
    return Signal(kind=SignalKind.UPDATE, raw_text=raw, status=TradeStatus.NEEDS_REVIEW,
                  confidence=0.6, notes=notes)


# --------------------------------------------------------------------------- #
# Validacije (sigurnost)
# --------------------------------------------------------------------------- #
def _validate_direction(sig: Signal) -> None:
    """LONG => stop < entry < TP ; SHORT => TP < entry < stop. Inace NEEDS_REVIEW."""
    if sig.entry is None or sig.stop is None:
        return
    tp = sig.take_profits[0].price if sig.take_profits else None
    if sig.side == Side.LONG:
        ok = sig.stop < sig.entry and (tp is None or tp > sig.entry)
    else:
        ok = sig.stop > sig.entry and (tp is None or tp < sig.entry)
    if not ok:
        sig.status = TradeStatus.NEEDS_REVIEW
        sig.confidence = min(sig.confidence, 0.4)
        sig.notes.append("SANITY FAIL: smjer/SL/TP nelogicni -> ne trguj automatski.")


def _check_skip_symbol(sig: Signal) -> None:
    base = (sig.pair or "").upper().replace("USDT", "")
    if base in SKIP_SYMBOLS or (sig.pair or "").upper() in SKIP_SYMBOLS:
        sig.status = TradeStatus.SKIPPED_NO_SYMBOL
        sig.notes.append(f"{sig.pair} nije na WEEX kripto futures -> SKIPPED_NO_SYMBOL.")
