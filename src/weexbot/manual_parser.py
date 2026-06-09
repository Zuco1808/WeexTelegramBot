"""Ekstrakcija "cinjenica" iz pojedine poruke za Trade Manager (Faza: TM).

Za razliku od parser.py (koji klasificira cijele A/C/B signale), ovdje vadimo
SVE prepoznatljive fragmente iz bilo koje poruke: par(ovi), smjer, ulaz, stop,
mete, te namjere upravljanja (move SL, breakeven, djelomicno zatvaranje, close).

Ovo je temelj za korelaciju Brandonovih multi-message signala.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .normalize import normalize

# Bazni simboli koje prepoznajemo kao parove (iz stvarnog kanala).
KNOWN_BASES: frozenset[str] = frozenset({
    "BTC", "ETH", "BNB", "XRP", "SOL", "ADA", "AVAX", "LINK", "TON", "TRX", "DOGE",
    "ASTER", "PUMP", "FF", "FARTCOIN", "ZEC", "EGLD", "ETC", "LTC", "ATOM", "HBAR",
    "XAU", "XAG", "XAUT",
})
# Puna imena -> ticker
NAME_MAP = {"ETHEREUM": "ETH", "BITCOIN": "BTC"}

# Broj: znamenke + opc. zarez/tocka, opc. "k"/"K" sufiks (56k = 56000).
# Negativni lookahead (?!\s*%) sprjecava hvatanje postotaka (npr. "50%") kao cijene.
_NUM = r"[\d][\d.,]*[kK]?(?!\s*%)"


def _to_float(s: str) -> float | None:
    s = s.strip().rstrip("$").rstrip(".")
    mult = 1.0
    if s[-1:] in ("k", "K"):
        mult = 1000.0
        s = s[:-1]
    s = s.replace(",", ".")
    if s.count(".") > 1:               # npr. "1.4.972" -> nevaljano
        return None
    try:
        return float(s) * mult
    except ValueError:
        return None


@dataclass
class MessageFacts:
    raw: str
    pairs: list[str] = field(default_factory=list)
    side: str | None = None              # LONG / SHORT
    entry: float | None = None
    entry_zone: tuple[float, float] | None = None
    stop_value: float | None = None
    stop_is_move: bool = False           # "stop TO x" / "now it will be at x" / "SL - x"
    targets: list[float] = field(default_factory=list)
    breakeven: bool = False              # SL to breakeven / to entry price
    partial_pct: int | None = None
    close: bool = False                  # stopped out / fully close
    open_hint: bool = False              # "trying/opening ... long/short"

    @property
    def is_building(self) -> bool:
        """Ima li polja koja grade NOVI signal (a ne upravljaju postojecim)?

        Sama rijec "short/long" u prozi (npr. "holding short") NE pokrece gradnju -
        treba i par, razine (entry/zona), ili "trying/opening" nagovjestaj.
        Poruke koje javljaju zatvaranje (close/stopped) nisu gradnja.
        """
        if self.close:
            return False
        has_levels = self.entry is not None or self.entry_zone is not None
        if self.open_hint:
            return bool(self.side or has_levels or self.pairs)
        if has_levels:
            return True
        return bool(self.side and self.pairs)

    @property
    def has_update(self) -> bool:
        return bool(self.breakeven or self.partial_pct or self.close
                    or (self.stop_value is not None))


# --- pojedinacni ekstraktori ------------------------------------------------ #
_PAIR_TOKEN = re.compile(r"\b([A-Z]{2,8})(USDT)?\b")


def _find_pairs(text: str) -> list[str]:
    found: list[str] = []
    # puna imena (Ethereum/Bitcoin)
    for name, base in NAME_MAP.items():
        if re.search(rf"\b{name}\b", text, re.I) and base not in found:
            found.append(base)
    for m in _PAIR_TOKEN.finditer(text):
        token, usdt = m.group(1), m.group(2)
        base = token
        if base in KNOWN_BASES or usdt:
            if base not in found:
                found.append(base)
    return found


def _find_side(text: str) -> str | None:
    m = re.search(r"\b(long|short)\b", text, re.I)
    return m.group(1).upper() if m else None


def _find_entry(text: str):
    m = re.search(
        r"\bentr(?:y|ies)\b(?:\s*(?:zone|range|point|levels?))?\s*:?\s*"
        rf"(?:market\s*/\s*)?({_NUM})(?:\s*[-/]\s*({_NUM}))?",
        text, re.I,
    )
    if not m:
        return None, None
    a = _to_float(m.group(1))
    b = _to_float(m.group(2)) if m.group(2) else None
    if a is None:
        return None, None
    if b is not None:
        # prava zona ima brojeve istog reda velicine; ako je omjer >10x,
        # drugi broj je sum -> tretiraj kao jedan ulaz
        lo, hi = min(a, b), max(a, b)
        if lo > 0 and hi / lo > 10:
            return a, None
        return None, (a, b)
    return a, None


# stop: keyword + (max 10 ne-znamenki) + broj. "move/to/now at/SL -" => move.
_STOP_RE = re.compile(
    r"(?P<kw>now it will be at|moving\s+sl|move\s+sl|move\s+stop|stop\s*-?\s*loss|"
    r"stoploss|stop|sl)\b[^0-9]{0,10}?(?P<num>" + _NUM + r")",
    re.I,
)
_MOVE_WORDS = re.compile(r"\b(?:to|moving|move|now it will be at)\b|sl\s*-", re.I)


def _find_stop(text: str):
    m = _STOP_RE.search(text)
    if not m:
        return None, False
    val = _to_float(m.group("num"))
    seg = text[m.start():m.end()]
    is_move = bool(_MOVE_WORDS.search(seg))
    return val, is_move


def _find_targets(text: str) -> list[float]:
    m = re.search(
        r"(targets?|take[-\s]?profits?|final take[-\s]?profit|first target|"
        r"\btp\b|\d+\s*target)\b[: ]*(?P<tail>.*)$",
        text, re.I,
    )
    if not m:
        return []
    tail = re.split(r"\b(sl|stop)\b", m.group("tail"), flags=re.I)[0]
    nums = [_to_float(x) for x in re.findall(_NUM, tail)]
    return [n for n in nums if n is not None][:5]


# Poruke koje vec obraduje glavni pipeline (Jeffrey/bot) ili su legenda -
# Trade Manager ih preskace da ne kontaminira stanje.
def is_handled_elsewhere(raw: str) -> bool:
    from .models import SignalKind
    from .parser import parse
    return parse(raw).kind in (SignalKind.JEFFREY, SignalKind.BOT, SignalKind.INFO)


def _find_partial_pct(text: str) -> int | None:
    m = re.search(r"(\d{1,3})\s*%\s*(?:take|close|off|fix)", text, re.I)
    if not m:
        m = re.search(r"(?:close|closing|take|fix|cut|trim)\s+(?:about\s+)?(\d{1,3})\s*%",
                      text, re.I)
    return int(m.group(1)) if m else None


_BREAKEVEN = re.compile(r"break\s*even|to entry price|stop to entry|sl to entry", re.I)
_CLOSE = re.compile(r"stopped out|got stopped|\bstopped\b|fully close|close (?:the )?rest|"
                    r"fully closed|close rest|closed by|closed at", re.I)
_OPEN_HINT = re.compile(r"\b(trying|opening|attempt|let'?s try|lets try|i'?m trying)\b", re.I)


def extract_facts(raw: str) -> MessageFacts:
    text = normalize(raw)
    entry, zone = _find_entry(text)
    stop_val, stop_move = _find_stop(text)
    return MessageFacts(
        raw=raw,
        pairs=_find_pairs(text),
        side=_find_side(text),
        entry=entry,
        entry_zone=zone,
        stop_value=stop_val,
        stop_is_move=stop_move,
        targets=_find_targets(text),
        breakeven=bool(_BREAKEVEN.search(text)),
        partial_pct=_find_partial_pct(text),
        close=bool(_CLOSE.search(text)),
        open_hint=bool(_OPEN_HINT.search(text)),
    )
