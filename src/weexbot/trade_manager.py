"""Trade Manager - korelacija Brandonovih multi-message signala i update poruka.

Stateful: prima poruke KRONOLOSKI i odrzava:
  - drafts:    nepotpuni signali u izgradnji ((par, tag) -> Draft)
  - positions: otvorene (paper) pozicije (par -> lista Position)
  - current_pair: zadnji "jaki" par, za fragmente bez para

Vise pozicija po paru (tag): Brandon zna drzati "long-term core" short PLUS
"scalp/added" poziciju na istom paru. Izmjene se usmjeravaju po tagu (npr.
"long-term short" -> CORE, "the portion you added" -> SCALP). Kad je nejasno
koja -> NEEDS_REVIEW ("u nedoumici pitaj").

Emitira listu TradeAction. Lokalna korelacijska logika; izvrsenje na WEEX je Faza 3.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .config import TM_STALE_TICKS
from .instruments import NOT_LISTED
from .manual_parser import MessageFacts, extract_facts, is_handled_elsewhere

# Iznad ovoga update poruke smatramo komentarom/naracijom, ne instrukcijom.
_NARRATIVE_LEN = 200

# Miksana poruka: zatvaranje prethodne + opis novog setupa ("re-entry now ...").
_REENTRY = re.compile(r"re-?entry|re-?enter|re-?open", re.I)

# Naznake koja je pod-pozicija u pitanju.
_CORE_HINT = re.compile(r"long[\s-]?term|core position|main channel|core short|core long", re.I)
_ADDED_HINT = re.compile(r"\badded\b|the portion|portion (?:i|you) added|whatever you added|"
                         r"the added|scalp add", re.I)


def _build_tag(text: str) -> str:
    return "CORE" if _CORE_HINT.search(text) else "SCALP"


def _update_tag_hint(text: str) -> str | None:
    if _CORE_HINT.search(text):
        return "CORE"
    if _ADDED_HINT.search(text):
        return "SCALP"
    return None


@dataclass
class Draft:
    pair: str
    tag: str = "SCALP"
    side: str | None = None
    entry: float | None = None
    entry_zone: tuple[float, float] | None = None
    entry_tiers: list[tuple[float, int]] = field(default_factory=list)
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
    entry_tiers: list[tuple[float, int]] = field(default_factory=list)  # (cijena, %)
    tag: str = "SCALP"          # SCALP (added/active) | CORE (long-term)
    status: str = "OPEN"        # OPEN | CLOSED | EXPIRED
    remaining_pct: int = 100
    last_tick: int = 0          # zadnja aktivnost (za stale expiry)


@dataclass
class TradeAction:
    message_id: str
    kind: str                   # OPEN|MOVE_SL|BREAKEVEN|PARTIAL_CLOSE|CLOSE|EXPIRE|...
    pair: str | None
    detail: dict = field(default_factory=dict)
    confidence: float = 1.0


class TradeManager:
    def __init__(self, db=None, stale_ticks: int = TM_STALE_TICKS):
        self.db = db                       # opcionalni weexbot.Database za perzistenciju
        self.stale_ticks = stale_ticks
        self.tick = 0
        self.drafts: dict[tuple[str, str], Draft] = {}
        self.positions: dict[str, list[Position]] = {}
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
        # miksana "stopped out + re-entry novi setup" poruka -> poseban put
        if (facts.close and _REENTRY.search(text)
                and (facts.entry is not None or facts.entry_zone)):
            out += self._handle_reentry(message_id, facts)
        elif facts.is_building:
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
        for lst in self.positions.values():
            for pos in lst:
                if pos.status == "OPEN" and (self.tick - pos.last_tick) > self.stale_ticks:
                    pos.status = "EXPIRED"
                    out.append(TradeAction(mid, "EXPIRE", pos.pair,
                                           {"tag": pos.tag,
                                            "reason": f"neaktivno > {self.stale_ticks} poruka"},
                                           confidence=0.5))
        return out

    def _persist(self, actions: list[TradeAction]) -> None:
        for a in actions:
            self.db.tm_insert_action(a.message_id, a.kind, a.pair, a.detail, a.confidence)
        for pair in {a.pair for a in actions if a.pair}:
            for pos in self.positions.get(pair, []):
                self.db.tm_upsert_position(
                    pos.pair, pos.tag, pos.side, pos.entry, pos.entry_zone, pos.stop,
                    pos.targets, pos.open_msg, pos.status, pos.remaining_pct,
                )

    # ------------------------------------------------------------------ #
    def _resolve_build_pair(self, facts: MessageFacts) -> tuple[str | None, str | None]:
        if facts.pairs:
            return facts.pairs[0], None
        if facts.unknown_ticker:
            return None, "novi signal s neprepoznatim simbolom (ne-kripto/nepoznat ticker)"
        if self.current_pair is not None:
            return self.current_pair, None
        return None, "signal bez prepoznatog para"

    def _handle_building(self, mid: str, facts: MessageFacts) -> list[TradeAction]:
        pair, reason = self._resolve_build_pair(facts)
        if pair is None:
            return [TradeAction(mid, "NEEDS_REVIEW", None,
                                {"reason": reason, "raw": facts.raw[:80]}, confidence=0.3)]
        if pair in NOT_LISTED:
            return [TradeAction(mid, "SKIPPED_NOT_LISTED", pair,
                                {"reason": "nije u podrzanoj WEEX listi"}, confidence=1.0)]

        self.current_pair = pair
        tag = _build_tag(facts.raw)
        key = (pair, tag)
        draft = self.drafts.setdefault(key, Draft(pair=pair, tag=tag, open_msg=mid))

        if facts.side:
            draft.side = facts.side
        if facts.entry is not None:
            draft.entry = facts.entry
        if facts.entry_zone:
            draft.entry_zone = facts.entry_zone
        if facts.entry_tiers:
            draft.entry_tiers = facts.entry_tiers
        if facts.stop_value is not None:          # u buildingu stop je POCETNI
            draft.stop = facts.stop_value
        if facts.targets:
            draft.targets = facts.targets

        if not draft.complete:
            return []                              # jos nepotpun; cekamo sljedece poruke

        # sanity: entry i stop istog reda velicine
        ref = draft.entry if draft.entry is not None else (
            (draft.entry_zone[0] + draft.entry_zone[1]) / 2)
        if ref and draft.stop and (ref == draft.stop or not (0.1 <= ref / draft.stop <= 10)):
            del self.drafts[key]
            return [TradeAction(mid, "NEEDS_REVIEW", pair,
                                {"reason": "entry/stop nelogicni (sum u ekstrakciji)",
                                 "entry": ref, "stop": draft.stop, "raw": facts.raw[:80]},
                                confidence=0.2)]

        # re-open zamjena: zatvori postojecu OTVORENU poziciju ISTOG taga
        lst = self.positions.setdefault(pair, [])
        extra: list[TradeAction] = []
        for old in lst:
            if old.status == "OPEN" and old.tag == tag:
                old.status = "CLOSED"
                extra.append(TradeAction(mid, "CLOSE", pair,
                                         {"tag": tag, "reason": "reopened/replaced"}))
        pos = Position(pair=pair, side=draft.side, entry=draft.entry,
                       entry_zone=draft.entry_zone, stop=draft.stop, targets=draft.targets,
                       entry_tiers=draft.entry_tiers, open_msg=mid, tag=tag, last_tick=self.tick)
        lst.append(pos)
        del self.drafts[key]
        return extra + [TradeAction(mid, "OPEN", pair, {
            "tag": tag, "side": pos.side, "entry": pos.entry, "entry_zone": pos.entry_zone,
            "entry_tiers": pos.entry_tiers, "stop": pos.stop, "targets": pos.targets,
        })]

    def _handle_reentry(self, mid: str, facts: MessageFacts) -> list[TradeAction]:
        """Poruka koja zatvara prethodnu poziciju I opisuje novi setup.

        Sigurno: zatvori prethodnu (stopped out) ako je jednoznacna, a NOVI setup
        salji u rucni pregled - tako management-tekst novog plana (take 50%,
        breakeven, close rest) NE padne kao izmjena na staru poziciju.
        """
        out: list[TradeAction] = []
        opens = self.all_open()
        if len(opens) == 1:
            opens[0].status = "CLOSED"
            out.append(TradeAction(mid, "CLOSE", opens[0].pair,
                                   {"tag": opens[0].tag, "reason": "stopped out (re-entry poruka)"}))
        new_pair = facts.pairs[0] if facts.pairs else None
        out.append(TradeAction(mid, "NEEDS_REVIEW", new_pair, {
            "reason": "re-entry: novi setup u poruci sa zatvaranjem - otvori rucno",
            "entry": facts.entry or facts.entry_zone, "stop": facts.stop_value,
            "targets": facts.targets, "raw": facts.raw[:80],
        }, confidence=0.4))
        return out

    # ------------------------------------------------------------------ #
    def _open_for(self, pair: str) -> list[Position]:
        return [p for p in self.positions.get(pair, []) if p.status == "OPEN"]

    def _open_count(self) -> int:
        return sum(len(self._open_for(p)) for p in self.positions)

    def _resolve_update_pairs(self, facts: MessageFacts) -> tuple[list[str], str | None]:
        open_pairs = [p for p in self.positions if self._open_for(p)]
        if facts.pairs:
            known = [p for p in facts.pairs if p in open_pairs]
            if known:
                return known, None
            return [], f"update za par bez otvorene pozicije: {facts.pairs}"
        n = self._open_count()
        if n == 1:
            return open_pairs, None
        if n == 0:
            return [], "update bez otvorenih pozicija"
        # vise pozicija, ali sve na ISTOM paru -> par je jasan; tag rjesava koja
        if len(open_pairs) == 1:
            return open_pairs, None
        return [], f"dvosmisleno: {n} otvorenih pozicija, par nije naveden"

    def _select_position(self, pair: str, tag_hint: str | None
                         ) -> tuple[Position | None, str | None]:
        cands = self._open_for(pair)
        if len(cands) == 1:
            return cands[0], None
        # vise pozicija za isti par -> trazimo tag
        if tag_hint:
            sel = [p for p in cands if p.tag == tag_hint]
            if len(sel) == 1:
                return sel[0], None
        return None, f"vise pozicija za {pair} (core/scalp) - nejasno koja"

    def _handle_update(self, mid: str, facts: MessageFacts) -> list[TradeAction]:
        pairs, reason = self._resolve_update_pairs(facts)
        if not pairs:
            return [TradeAction(mid, "NEEDS_REVIEW", None,
                                {"reason": reason, "raw": facts.raw[:80]}, confidence=0.3)]

        tag_hint = _update_tag_hint(facts.raw)
        out: list[TradeAction] = []
        for pair in pairs:
            pos, amb = self._select_position(pair, tag_hint)
            if pos is None:
                out.append(TradeAction(mid, "NEEDS_REVIEW", pair,
                                       {"reason": amb, "raw": facts.raw[:80]}, confidence=0.3))
                continue
            out += self._apply_update(mid, facts, pos, single_target=(len(pairs) == 1))
        return out

    def _apply_update(self, mid: str, facts: MessageFacts, pos: Position,
                      single_target: bool) -> list[TradeAction]:
        pos.last_tick = self.tick
        d = {"tag": pos.tag}
        out: list[TradeAction] = []
        if facts.breakeven:
            pos.stop = pos.entry if pos.entry is not None else pos.stop
            out.append(TradeAction(mid, "BREAKEVEN", pos.pair, {**d, "new_stop": pos.stop}))
        elif facts.stop_value is not None:
            pos.stop = facts.stop_value
            out.append(TradeAction(mid, "MOVE_SL", pos.pair, {**d, "new_stop": facts.stop_value}))
        if facts.partial_pct is not None:
            pos.remaining_pct = max(0, pos.remaining_pct - facts.partial_pct)
            out.append(TradeAction(mid, "PARTIAL_CLOSE", pos.pair,
                                   {**d, "pct": facts.partial_pct, "remaining": pos.remaining_pct}))
        if facts.close:
            if single_target:
                pos.status = "CLOSED"
                out.append(TradeAction(mid, "CLOSE", pos.pair, d))
            else:
                out.append(TradeAction(mid, "NEEDS_REVIEW", pos.pair,
                                       {**d, "reason": "close uz vise parova - provjeri rucno"},
                                       confidence=0.3))
        return out

    # ------------------------------------------------------------------ #
    def all_open(self) -> list[Position]:
        return [p for lst in self.positions.values() for p in lst if p.status == "OPEN"]

    def position(self, pair: str, tag: str | None = None) -> Position | None:
        opens = self._open_for(pair)
        if tag is not None:
            return next((p for p in opens if p.tag == tag), None)
        return opens[0] if opens else None

    def open_positions(self) -> dict[str, Position]:
        """Pogled par -> jedna otvorena pozicija (preferira SCALP). Za visestruke
        pozicije po paru koristi all_open()/position(pair, tag)."""
        out: dict[str, Position] = {}
        for pair in self.positions:
            opens = self._open_for(pair)
            if not opens:
                continue
            scalp = [p for p in opens if p.tag == "SCALP"]
            out[pair] = scalp[0] if scalp else opens[0]
        return out
