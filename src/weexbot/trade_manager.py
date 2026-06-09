"""Trade Manager - korelacija Brandonovih multi-message signala i update poruka.

Stateful: prima poruke KRONOLOSKI i odrzava:
  - drafts:    nepotpuni signali u izgradnji (par -> Draft)
  - positions: otvorene (paper) pozicije (par -> Position)
  - current_pair: zadnji "jaki" par, za fragmente bez para

Emitira listu TradeAction (OPEN / MOVE_SL / BREAKEVEN / PARTIAL_CLOSE / CLOSE /
NEEDS_REVIEW). Pravilo "u nedoumici pitaj": ako update poruku nije moguce
jednoznacno povezati s pozicijom -> NEEDS_REVIEW (ne dira se nista).

Opseg/ogranicenja: jedna aktivna pozicija po paru (hedge-slucajevi se oznacavaju
za rucni pregled). Ovo je lokalna korelacijska logika; izvrsenje na WEEX je Faza 3.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import TM_STALE_TICKS
from .manual_parser import MessageFacts, extract_facts, is_handled_elsewhere

# Iznad ovoga update poruke smatramo komentarom/naracijom, ne instrukcijom.
_NARRATIVE_LEN = 200


@dataclass
class Draft:
    pair: str
    side: str | None = None
    entry: float | None = None
    entry_zone: tuple[float, float] | None = None
    stop: float | None = None
    targets: list[float] = field(default_factory=list)
    open_msg: str | None = None

    @property
    def complete(self) -> bool:
        return bool(self.side and (self.entry is not None or self.entry_zone)
                    and self.stop is not None)


@dataclass
class Position:
    pair: str
    side: str
    entry: float | None
    entry_zone: tuple[float, float] | None
    stop: float | None
    targets: list[float]
    open_msg: str
    status: str = "OPEN"        # OPEN | CLOSED | EXPIRED
    remaining_pct: int = 100
    last_tick: int = 0          # zadnja aktivnost (za stale expiry)


@dataclass
class TradeAction:
    message_id: str
    kind: str                   # OPEN|MOVE_SL|BREAKEVEN|PARTIAL_CLOSE|CLOSE|NEEDS_REVIEW
    pair: str | None
    detail: dict = field(default_factory=dict)
    confidence: float = 1.0


class TradeManager:
    def __init__(self, db=None, stale_ticks: int = TM_STALE_TICKS):
        self.db = db                       # opcionalni weexbot.Database za perzistenciju
        self.stale_ticks = stale_ticks
        self.tick = 0
        self.drafts: dict[str, Draft] = {}
        self.positions: dict[str, Position] = {}
        self.current_pair: str | None = None
        self.actions: list[TradeAction] = []

    # ------------------------------------------------------------------ #
    def process(self, message_id: str, text: str) -> list[TradeAction]:
        self.tick += 1
        out: list[TradeAction] = self._expire_stale(message_id)

        # Jeffrey/bot/legenda obraduje pipeline; TM se bavi Brandon manualom + updateima.
        if is_handled_elsewhere(text):
            return self._finish(out)

        facts = extract_facts(text)
        if facts.is_building:
            out += self._handle_building(message_id, facts)
        elif facts.has_update and len(text) <= _NARRATIVE_LEN:
            # kratke poruke = instrukcije; duga proza = komentar -> ignoriraj
            out += self._handle_update(message_id, facts)
        # cista chatter (ni building ni update) -> nista

        return self._finish(out)

    def _finish(self, out: list[TradeAction]) -> list[TradeAction]:
        if self.db is not None:
            self._persist(out)
        self.actions += out
        return out

    def _expire_stale(self, mid: str) -> list[TradeAction]:
        out: list[TradeAction] = []
        for pair, pos in self.positions.items():
            if pos.status == "OPEN" and (self.tick - pos.last_tick) > self.stale_ticks:
                pos.status = "EXPIRED"
                out.append(TradeAction(mid, "EXPIRE", pair,
                                       {"reason": f"neaktivno > {self.stale_ticks} poruka"},
                                       confidence=0.5))
        return out

    def _persist(self, actions: list[TradeAction]) -> None:
        for a in actions:
            self.db.tm_insert_action(a.message_id, a.kind, a.pair, a.detail, a.confidence)
        for pair in {a.pair for a in actions if a.pair}:
            pos = self.positions.get(pair)
            if pos is not None:
                self.db.tm_upsert_position(
                    pos.pair, pos.side, pos.entry, pos.entry_zone, pos.stop,
                    pos.targets, pos.open_msg, pos.status, pos.remaining_pct,
                )

    # ------------------------------------------------------------------ #
    def _resolve_build_pair(self, facts: MessageFacts) -> tuple[str | None, str | None]:
        """(pair, reason_if_none).

        - eksplicitan par -> taj par
        - bez para, ali izgleda kao SAMOSTALAN setup (ima smjer ili stop) ->
          vjerojatno novi instrument s neprepoznatim tickerom (npr. OIL/PLTR)
          -> NE preuzimaj current_pair (inace bi "oteo" tudu poziciju)
        - bez para, samo razine (cisti nastavak-fragment) -> current_pair
        """
        if facts.pairs:
            return facts.pairs[0], None
        if facts.side or facts.stop_value is not None:
            return None, "novi signal s neprepoznatim simbolom (ne-kripto/nepoznat ticker)"
        if self.current_pair is not None:
            return self.current_pair, None
        return None, "signal bez prepoznatog para"

    def _handle_building(self, mid: str, facts: MessageFacts) -> list[TradeAction]:
        pair, reason = self._resolve_build_pair(facts)
        if pair is None:
            return [TradeAction(mid, "NEEDS_REVIEW", None,
                                {"reason": reason, "raw": facts.raw[:80]},
                                confidence=0.3)]
        self.current_pair = pair
        draft = self.drafts.setdefault(pair, Draft(pair=pair, open_msg=mid))

        if facts.side:
            draft.side = facts.side
        if facts.entry is not None:
            draft.entry = facts.entry
        if facts.entry_zone:
            draft.entry_zone = facts.entry_zone
        # u building kontekstu stop je POCETNI stop (ne move)
        if facts.stop_value is not None:
            draft.stop = facts.stop_value
        if facts.targets:
            draft.targets = facts.targets

        if draft.complete:
            # sanity: entry i stop moraju biti istog reda velicine (real ~unutar 20%)
            ref = draft.entry if draft.entry is not None else (
                (draft.entry_zone[0] + draft.entry_zone[1]) / 2)
            if ref and draft.stop and (ref == draft.stop
                                       or not (0.1 <= ref / draft.stop <= 10)):
                del self.drafts[pair]
                return [TradeAction(mid, "NEEDS_REVIEW", pair,
                                    {"reason": "entry/stop nelogicni (sum u ekstrakciji)",
                                     "entry": ref, "stop": draft.stop, "raw": facts.raw[:80]},
                                    confidence=0.2)]
            extra: list[TradeAction] = []
            old = self.positions.get(pair)
            if old is not None and old.status == "OPEN":
                old.status = "CLOSED"
                extra.append(TradeAction(mid, "CLOSE", pair,
                                         {"reason": "reopened/replaced"}))
            pos = Position(
                pair=pair, side=draft.side, entry=draft.entry,
                entry_zone=draft.entry_zone, stop=draft.stop,
                targets=draft.targets, open_msg=mid, last_tick=self.tick,
            )
            self.positions[pair] = pos
            del self.drafts[pair]
            return extra + [TradeAction(mid, "OPEN", pair, {
                "side": pos.side, "entry": pos.entry, "entry_zone": pos.entry_zone,
                "stop": pos.stop, "targets": pos.targets,
            })]
        return []   # jos nepotpun nacrt; cekamo sljedece poruke

    # ------------------------------------------------------------------ #
    def _resolve_update_pairs(self, facts: MessageFacts) -> tuple[list[str], str | None]:
        """Vrati (pairs, reason_if_ambiguous).

        Pravilo "u nedoumici pitaj": eksplicitan par ima prednost; bez para
        koristimo poziciju SAMO ako je tocno jedna otvorena. Vise otvorenih bez
        navedenog para -> NEEDS_REVIEW (NE oslanjamo se na current_pair za izmjene).
        """
        open_pos = [p for p, pos in self.positions.items() if pos.status == "OPEN"]
        if facts.pairs:
            known = [p for p in facts.pairs if p in self.positions
                     and self.positions[p].status == "OPEN"]
            if known:
                return known, None
            return [], f"update za par bez otvorene pozicije: {facts.pairs}"
        if len(open_pos) == 1:
            return open_pos, None
        if len(open_pos) == 0:
            return [], "update bez otvorenih pozicija"
        return [], f"dvosmisleno: {len(open_pos)} otvorenih pozicija, par nije naveden"

    def _handle_update(self, mid: str, facts: MessageFacts) -> list[TradeAction]:
        pairs, reason = self._resolve_update_pairs(facts)
        if not pairs:
            return [TradeAction(mid, "NEEDS_REVIEW", None,
                                {"reason": reason, "raw": facts.raw[:80]}, confidence=0.3)]

        out: list[TradeAction] = []
        for pair in pairs:
            pos = self.positions[pair]
            pos.last_tick = self.tick          # bilo kakva izmjena = aktivnost
            if facts.breakeven:
                pos.stop = pos.entry if pos.entry is not None else pos.stop
                out.append(TradeAction(mid, "BREAKEVEN", pair, {"new_stop": pos.stop}))
            elif facts.stop_value is not None:
                pos.stop = facts.stop_value
                out.append(TradeAction(mid, "MOVE_SL", pair, {"new_stop": facts.stop_value}))
            if facts.partial_pct is not None:
                pos.remaining_pct = max(0, pos.remaining_pct - facts.partial_pct)
                out.append(TradeAction(mid, "PARTIAL_CLOSE", pair,
                                       {"pct": facts.partial_pct, "remaining": pos.remaining_pct}))
            if facts.close:
                # puni close primjenjujemo samo kad je par jednoznacan; vise parova
                # uz "stopped/closed" je cesto "X stopped, Y aktivan" -> rucni pregled
                if len(pairs) == 1:
                    pos.status = "CLOSED"
                    out.append(TradeAction(mid, "CLOSE", pair, {}))
                else:
                    out.append(TradeAction(mid, "NEEDS_REVIEW", pair,
                                           {"reason": "close uz vise parova - provjeri rucno"},
                                           confidence=0.3))
        return out

    # ------------------------------------------------------------------ #
    def open_positions(self) -> dict[str, Position]:
        return {p: pos for p, pos in self.positions.items() if pos.status == "OPEN"}
