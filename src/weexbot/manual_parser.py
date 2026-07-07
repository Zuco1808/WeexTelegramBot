"""Ekstrakcija "cinjenica" iz pojedine poruke za Trade Manager (Faza: TM).

Za razliku od parser.py (koji klasificira cijele A/C/B signale), ovdje vadimo
SVE prepoznatljive fragmente iz bilo koje poruke: par(ovi), smjer, ulaz, stop,
mete, te namjere upravljanja (move SL, breakeven, djelomicno zatvaranje, close).

Ovo je temelj za korelaciju Brandonovih multi-message signala.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .instruments import CRYPTO_BASES, TRADFI_BASES
from .normalize import normalize

# Sve sto prepoznajemo kao "par" = kripto + TradFi/RWA (mapiranje u instruments.py).
KNOWN_BASES: frozenset[str] = CRYPTO_BASES | TRADFI_BASES
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
    entry_tiers: list[tuple[float, int]] = field(default_factory=list)  # (cijena, %)
    stop_value: float | None = None
    stop_is_move: bool = False           # "stop TO x" / "now it will be at x" / "SL - x"
    targets: list[float] = field(default_factory=list)
    breakeven: bool = False              # SL to breakeven / to entry price
    partial_pct: int | None = None
    close: bool = False                  # stopped out / fully close
    open_hint: bool = False              # "trying/opening ... long/short"
    unknown_ticker: bool = False         # vodeci neprepoznat ticker (novi instrument)

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
_PAIR_TOKEN = re.compile(r"\b([A-Z]{2,10})\b")
_LEADING_TOKEN = re.compile(r"\s*([A-Z]{2,10})\b")
# "$TICKER" - kanal eksplicitno oznacava simbol dolarom (npr. "$WIF SHORT").
# Zahtijeva slovo iza $ pa "$10,000" (iznos) ne prolazi.
_DOLLAR_TOKEN = re.compile(r"\$([A-Z][A-Z0-9]{1,9})\b")


def _find_pairs(text: str) -> list[str]:
    found: list[str] = []
    # $TICKER: eksplicitno oznacen simbol -> par i kad nije u registru (nova moneta).
    for m in _DOLLAR_TOKEN.finditer(text):
        tok = m.group(1)
        base = tok[:-4] if tok.endswith("USDT") and len(tok) > 4 else tok
        if base not in found:
            found.append(base)
    # puna imena (Ethereum/Bitcoin)
    for name, base in NAME_MAP.items():
        if re.search(rf"\b{name}\b", text, re.I) and base not in found:
            found.append(base)
    for m in _PAIR_TOKEN.finditer(text):
        tok = m.group(1)
        if tok.endswith("USDT") and len(tok) > 4:
            base = tok[:-4]                 # XYZUSDT -> XYZ (svaki *USDT je par)
        elif tok in KNOWN_BASES:
            base = tok
        else:
            continue
        if base not in found:
            found.append(base)
    return found


def _has_unknown_ticker(text: str, pairs: list[str]) -> bool:
    """Vodeci ALLCAPS token koji NIJE prepoznat kao par => novi/nepoznat instrument."""
    if pairs:
        return False
    m = _LEADING_TOKEN.match(text)
    if not m:
        return False
    tok = m.group(1)
    return not tok.endswith("USDT") and tok not in KNOWN_BASES


def _find_side(text: str) -> str | None:
    # "long-term" / "long term" nije smjer pozicije -> preskoci taj "long"
    m = re.search(r"\b(long|short)\b(?!\s*-?\s*term)", text, re.I)
    return m.group(1).upper() if m else None


# Tiered ulaz s alokacijom: "1. 136.5 - 30%   2. 128 - 70%"
_ENTRY_TIER = re.compile(r"\d+\.\s*(" + _NUM + r")\s*-\s*(\d{1,3})\s*%")


def _entry_section(text: str) -> str:
    """Tekst nakon 'Entry...' kljuca, odrezan na prvom SL/Stop/Target/TP."""
    m = re.search(r"\bentr(?:y|ies)\b(?:\s*(?:zone|range|point|levels?))?\s*:?\s*(?P<rest>.*)",
                  text, re.I)
    if not m:
        return ""
    return re.split(r"\b(sl|stop|stoploss|target|targets|tp)\b", m.group("rest"), flags=re.I)[0]


def _find_entry_tiers(text: str) -> list[tuple[float, int]]:
    """Lista (cijena, postotak) za tiered ulaze; prazno ako nema alokacija."""
    out: list[tuple[float, int]] = []
    for m in _ENTRY_TIER.finditer(_entry_section(text)):
        price = _to_float(m.group(1))
        if price is not None:
            out.append((price, int(m.group(2))))
    return out


def _find_entry(text: str):
    rest = _entry_section(text)
    if not rest:
        return None, None

    # tiered ulaz s alokacijom: "1. 136.5 - 30%  2. 128 - 70%"
    tiered = re.findall(r"\d+\.\s*(" + _NUM + r")\s*-\s*\d+\s*%", rest)
    if len(tiered) >= 2:
        a, b = _to_float(tiered[0]), _to_float(tiered[1])
        if a is not None and b is not None:
            return None, (a, b)

    # standardno: opc. ordinal "1.", opc. "market /", cijena, opc. raspon
    m2 = re.search(r"(?:\d+\.\s+)?(?:market\s*/\s*)?(" + _NUM + r")(?:\s*[-/]\s*(" + _NUM + r"))?", rest)
    if not m2:
        return None, None
    a = _to_float(m2.group(1))
    b = _to_float(m2.group(2)) if m2.group(2) else None
    if a is None:
        return None, None
    # "Second entry: X" -> druga granica zone
    if b is None:
        sec = re.search(r"second\s+entry\s*:?\s*(" + _NUM + r")", text, re.I)
        if sec:
            b = _to_float(sec.group(1))
    if b is not None:
        lo, hi = min(a, b), max(a, b)
        if lo > 0 and hi / lo > 10:        # omjer >10x -> drugi broj je sum
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
    # 1) numerirani TP-ovi: "1TP - 311", "TP1: 96", "TP - 73", "2TP-330", "3TP - 347"
    numbered = re.findall(r"\b\d?\s*tp\s*\d?\s*[-:]\s*(" + _NUM + r")", text, re.I)
    if numbered:
        out = [_to_float(x) for x in numbered]
        return [n for n in out if n is not None][:5]
    # 2) labelirani: "Target(s): a / b / c", "First/Final take-profit: x"
    m = re.search(r"(?:targets?|take[-\s]?profits?|final take[-\s]?profit|first target)"
                  r"\s*:?\s*(?P<tail>.*)$", text, re.I)
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
_CLOSE = re.compile(r"stopped out|got stopped|\bstopped\b|fully close|full close|"
                    r"close (?:the )?rest|fully closed|close rest|closed by|closed at|"
                    r"clos\w+[^.]{0,40}complet", re.I)
_OPEN_HINT = re.compile(r"\b(trying|opening|attempt|let'?s try|lets try|i'?m trying)\b", re.I)


def extract_facts(raw: str) -> MessageFacts:
    text = normalize(raw)
    entry, zone = _find_entry(text)
    stop_val, stop_move = _find_stop(text)
    pairs = _find_pairs(text)
    return MessageFacts(
        raw=raw,
        pairs=pairs,
        unknown_ticker=_has_unknown_ticker(text, pairs),
        side=_find_side(text),
        entry=entry,
        entry_zone=zone,
        entry_tiers=_find_entry_tiers(text),
        stop_value=stop_val,
        stop_is_move=stop_move,
        targets=_find_targets(text),
        breakeven=bool(_BREAKEVEN.search(text)),
        partial_pct=_find_partial_pct(text),
        close=bool(_CLOSE.search(text)),
        open_hint=bool(_OPEN_HINT.search(text)),
    )
