"""Pokrece parser nad porukama i ispisuje pregled + position sizing (100 USDT).

Izvor poruka (po prioritetu):
  1) data/messages_all.jsonl  (ako postoji - rezultat extract_messages.py)
  2) ugradeni uzorak iz tests/samples.py  (50 poruka, radi bez HTML-a)

Izlaz:
  - ispis tablice u terminal
  - data/parsed.jsonl  (svi parsirani signali)
"""
import json
import os
import sys

# omoguci 'import weexbot' bez instalacije
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from weexbot import parse, SignalKind, TradeStatus           # noqa: E402
from weexbot.config import CAPITAL_USDT, RISK_PCT_SCALP      # noqa: E402
from weexbot.risk import plan_position                       # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
ALL_JSONL = os.path.join(DATA_DIR, "messages_all.jsonl")


def load_messages() -> list[str]:
    if os.path.exists(ALL_JSONL):
        texts = []
        with open(ALL_JSONL, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    texts.append(json.loads(line)["text"])
        print(f"Izvor: {ALL_JSONL} ({len(texts)} poruka)\n")
        return texts
    from tests.samples import SAMPLES  # type: ignore
    print(f"Izvor: ugradeni uzorak tests/samples.py ({len(SAMPLES)} poruka)\n")
    return [text for _id, text, _kind in SAMPLES]


def main() -> int:
    texts = load_messages()
    signals = [parse(t) for t in texts]

    # 1) Sazetak po vrsti
    counts: dict[str, int] = {}
    for s in signals:
        counts[s.kind.value] = counts.get(s.kind.value, 0) + 1
    print("=== Sazetak po formatu ===")
    for kind in SignalKind:
        if counts.get(kind.value):
            print(f"  {kind.value:12s}: {counts[kind.value]}")
    tradable = [s for s in signals if s.is_tradable]
    print(f"\n  TRADABLE (Faza 1): {len(tradable)}")

    # 2) Detalji TRADABLE signala + position sizing za 100 USDT
    print(f"\n=== TRADABLE signali  (kapital {CAPITAL_USDT:g} USDT, "
          f"rizik {RISK_PCT_SCALP*100:g}%) ===")
    print(f"{'PAR':10s} {'SMJER':6s} {'ENTRY':>11s} {'STOP':>11s} "
          f"{'TP':>11s} {'LEV':>5s} {'QTY':>12s} {'NOTIO':>9s} {'MARG':>8s}")
    for s in tradable:
        tp = s.take_profits[0].price if s.take_profits else 0.0
        plan = plan_position(s.entry, s.stop, s.leverage)
        if not plan:
            continue
        print(f"{s.pair:10s} {s.side.value:6s} {s.entry:>11.4g} {s.stop:>11.4g} "
              f"{tp:>11.4g} {s.leverage:>4.0f}x {plan.quantity:>12.6f} "
              f"{plan.notional:>9.2f} {plan.margin or 0:>8.2f}")

    # 3) Sve sto NIJE jasno -> rucni pregled / preskoceno
    flagged = [s for s in signals if s.status in
               (TradeStatus.NEEDS_REVIEW, TradeStatus.SKIPPED_NO_SYMBOL)]
    print(f"\n=== Za rucni pregled / preskoceno: {len(flagged)} ===")

    # 4) zapisi parsed.jsonl
    os.makedirs(DATA_DIR, exist_ok=True)
    out = os.path.join(DATA_DIR, "parsed.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for s in signals:
            f.write(json.dumps(s.to_dict(), ensure_ascii=False) + "\n")
    print(f"\nSpremljeno: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
