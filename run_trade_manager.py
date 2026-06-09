"""Replay cijelog izvoza kroz Trade Manager i ispis vremenske linije akcija.

Pokretanje:
    python run_trade_manager.py            # sazetak + zadnjih N akcija
    python run_trade_manager.py --all      # ispis svih akcija
    python run_trade_manager.py --review   # samo NEEDS_REVIEW
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from weexbot import Database, TradeManager        # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
ALL_JSONL = os.path.join(DATA_DIR, "messages_all.jsonl")
DB_PATH = os.path.join(DATA_DIR, "weex_paper.db")


def load_messages():
    if os.path.exists(ALL_JSONL):
        out = []
        with open(ALL_JSONL, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    out.append((r["id"], r["text"]))
        print(f"Izvor: {ALL_JSONL} ({len(out)} poruka)\n")
        return out
    from tests.samples import SAMPLES  # type: ignore
    return [(f"sample-{i}", t) for i, t, _k in SAMPLES]


def fmt(a) -> str:
    d = {k: v for k, v in a.detail.items() if k != "raw"}
    return f"[{a.message_id:>11s}] {a.kind:14s} {a.pair or '-':6s} {d}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--review", action="store_true")
    args = ap.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)
    db = Database(DB_PATH)
    tm = TradeManager(db=db)
    for mid, text in load_messages():
        tm.process(mid, text)
    print(f"(perzistirano u {DB_PATH}: tm_positions={db.count('tm_positions')}, "
          f"tm_actions={db.count('tm_actions')})\n")

    counts: dict[str, int] = {}
    for a in tm.actions:
        counts[a.kind] = counts.get(a.kind, 0) + 1

    print("=== Sazetak akcija ===")
    for k in ("OPEN", "MOVE_SL", "BREAKEVEN", "PARTIAL_CLOSE", "CLOSE", "EXPIRE",
              "SKIPPED_NON_CRYPTO", "NEEDS_REVIEW"):
        if counts.get(k):
            print(f"  {k:14s}: {counts[k]}")
    print(f"\n  Otvorenih pozicija na kraju: {len(tm.open_positions())}")
    for p, pos in tm.open_positions().items():
        print(f"    {p:6s} {pos.side:5s} entry={pos.entry or pos.entry_zone} "
              f"stop={pos.stop} ostalo={pos.remaining_pct}%")

    if args.review:
        print("\n=== NEEDS_REVIEW ===")
        for a in tm.actions:
            if a.kind == "NEEDS_REVIEW":
                print(fmt(a))
    else:
        shown = tm.actions if args.all else tm.actions[-25:]
        print(f"\n=== Akcije ({'sve' if args.all else 'zadnjih 25'}) ===")
        for a in shown:
            print(fmt(a))
    return 0


if __name__ == "__main__":
    sys.exit(main())
