"""Normalizirani modeli signala - jedinstveni izlaz parsera bez obzira na format."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum


class Side(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class SignalKind(str, Enum):
    """Obitelj poruke (vidi analizu formata u README-u)."""
    JEFFREY = "A_jeffrey"   # scalp, precizan, $TICKER, jedan TP
    ZONE = "B_zone"         # Brandon intraday, raspon ulaza, vise TP
    BOT = "C_bot"           # bot scalp, timeframe, Price/TP/SL
    MANUAL = "D_manual"     # rucni analiticar (Target:/Stoploss:/Entry:)
    UPDATE = "E_update"     # izmjena pozicije (Move SL, Fix %, breakeven...)
    INFO = "INFO"           # legenda / pravila / chatter koji je info
    UNKNOWN = "UNKNOWN"     # nije prepoznato (npr. cisti komentar)


class TradeStatus(str, Enum):
    TRADABLE = "TRADABLE"                    # spremno za (paper) izvrsenje u Fazi 1
    SKIPPED_NO_SYMBOL = "SKIPPED_NO_SYMBOL"  # simbol nije na WEEX (npr. metali)
    NOT_TRADED_PHASE1 = "NOT_TRADED_PHASE1"  # validan format ali izvan opsega Faze 1 (B)
    SKIPPED_EXPOSURE = "SKIPPED_EXPOSURE"    # odbijeno zbog limita istovremene izlozenosti
    NEEDS_REVIEW = "NEEDS_REVIEW"            # dvosmisleno / sanity fail -> covjek odlucuje
    INFO = "INFO"                            # ignorirati (legenda/komentar)


@dataclass
class TakeProfit:
    price: float
    fraction: float | None = None      # 0.75 = fiksiraj 75%; None = nepoznato/cijela
    move_sl_after: str | None = None   # "breakeven" | "tp2" | None


@dataclass
class Signal:
    kind: SignalKind
    raw_text: str
    pair: str | None = None
    side: Side | None = None
    entry: float | None = None
    entry_zone: tuple[float, float] | None = None
    stop: float | None = None
    take_profits: list[TakeProfit] = field(default_factory=list)
    leverage: float | None = None
    leverage_range: tuple[float, float] | None = None
    timeframe: str | None = None
    status: TradeStatus = TradeStatus.NEEDS_REVIEW
    confidence: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def is_tradable(self) -> bool:
        return self.status == TradeStatus.TRADABLE

    def to_dict(self) -> dict:
        d = asdict(self)
        d["kind"] = self.kind.value
        d["status"] = self.status.value
        d["side"] = self.side.value if self.side else None
        return d
