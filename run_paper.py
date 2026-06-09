"""Faza 2 runner: ucitaj poruke -> pipeline -> SQLite paper baza -> izvjestaj.

Pokretanje:
    python run_paper.py                # koristi data/messages_all.jsonl ili ugradeni uzorak
    python run_paper.py --keep         # ne brise postojecu bazu (test perzistencije)

Demonstrira i IDEMPOTENTNOST: nakon prvog prolaza, drugi prolaz ne stvara
nijednu novu poziciju (sve poruke su SKIPPED_DUPLICATE).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from weexbot import Database, Pipeline                       # noqa: E402
from weexbot.config import CAPITAL_USDT, RISK_PCT_SCALP      # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.path.join(DATA_DIR, "weex_paper.db")
ALL_JSONL = os.path.join(DATA_DIR, "messages_all.jsonl")


def load_messages() -> list[tuple[str, str, str | None]]:
    if os.path.exists(ALL_JSONL):
        out = []
        with open(ALL_JSONL, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                out.append((r["id"], r["text"], r.get("date")))
        print(f"Izvor: {ALL_JSONL} ({len(out)} poruka)\n")
        return out
    from tests.samples import SAMPLES  # type: ignore
    print(f"Izvor: ugradeni uzorak ({len(SAMPLES)} poruka)\n")
    return [(f"sample-{i}", text, None) for i, text, _k in SAMPLES]


def run_pass(pipe: Pipeline, messages) -> dict[str, int]:
    actions: dict[str, int] = {}
    for mid, text, date in messages:
        res = pipe.process(mid, text, date)
        actions[res.action] = actions.get(res.action, 0) + 1
    return actions


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="ne brisi postojecu bazu")
    args = ap.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)
    if not args.keep and os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    messages = load_messages()
    db = Database(DB_PATH, starting_balance=CAPITAL_USDT)
    pipe = Pipeline(db, capital=CAPITAL_USDT, risk_pct=RISK_PCT_SCALP)

    print("=== Prolaz 1 ===")
    a1 = run_pass(pipe, messages)
    for k, v in sorted(a1.items()):
        print(f"  {k:18s}: {v}")

    print("\n=== Prolaz 2 (idempotentnost) ===")
    a2 = run_pass(pipe, messages)
    for k, v in sorted(a2.items()):
        print(f"  {k:18s}: {v}")
    novih = a2.get("POSITION_PLANNED", 0)
    print(f"  -> novih pozicija u 2. prolazu: {novih} (ocekivano 0)")

    print("\n=== Stanje baze ===")
    print(f"  signali:  {db.count('signals')}")
    print(f"  pozicije: {db.count('positions')}")
    print(f"  nalozi:   {db.count('orders')}")
    print(f"  audit:    {db.count('audit_log')}")
    print(f"  stanje racuna: {db.balance():.2f} USDT")
    print(f"  rezervirana margina (PLANNED): {db.total_reserved_margin():.2f} USDT")

    print("\n=== Planirane paper pozicije ===")
    print(f"{'SYMBOL':10s} {'SIDE':5s} {'ENTRY':>11s} {'STOP':>11s} "
          f"{'QTY':>12s} {'NOTIO':>9s} {'MARG':>8s}")
    for p in db.positions():
        print(f"{p['symbol']:10s} {p['side']:5s} {p['entry_price']:>11.4g} "
              f"{p['stop']:>11.4g} {p['quantity']:>12.6f} "
              f"{p['notional']:>9.2f} {p['margin'] or 0:>8.2f}")

    db.close()
    print(f"\nBaza spremljena: {DB_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
