"""Faza 3.5 - LIVE izvrsenje jednog signala (semi-auto).

Tok: parsiraj signal -> plan (sizing, zaokruzivanje, band) -> prikazi ->
ti potvrdis (--yes) -> ako je entry izvan +-1% banda i dan --wait, ceka da
cijena udje u bend pa plasira entry limit + preset SL/TP.

    # samo prikazi plan (nista se ne salje):
    python run_live_trade.py --text "$ETHUSDTlongentry - 2739.56; stop - 2632.84take - 2825.47; leverage - x11"

    # stvarno (semi-auto): postavi leverage + plasiraj kad je u bandu
    python run_live_trade.py --text "...signal..." --yes --wait
"""
import argparse
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

MAX_NOTIONAL = 50.0          # safety guard za prve live trejdove


def load_env(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def show_plan(p):
    print("\n=== PLAN ===")
    if not p.ok:
        print(f"  NE: {p.reason}")
        return
    print(f"  {p.symbol}  {p.side}  qty={p.quantity}  leverage x{p.leverage:g} isolated")
    print(f"  entry={p.entry}  stop={p.stop}  TP={p.take_profit}  (mark={p.mark})")
    print(f"  notional ~ {p.notional:.2f} USDT, marza ~ {p.margin:.2f} USDT, "
          f"rizik ~ {p.risk_usdt:.2f} USDT")
    print(f"  u bandu (+-1%): {p.in_band}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True, help="sirovi tekst signala")
    ap.add_argument("--yes", action="store_true", help="obavezno za stvarno slanje")
    ap.add_argument("--wait", action="store_true", help="cekaj da entry udje u +-1% bend")
    ap.add_argument("--poll", type=int, default=20, help="interval provjere cijene (s)")
    ap.add_argument("--timeout", type=int, default=1800, help="maks. cekanje (s)")
    ap.add_argument("--max-notional", type=float, default=MAX_NOTIONAL)
    args = ap.parse_args()

    load_env(os.path.join(ROOT, ".env"))
    from weexbot import parse
    from weexbot.live_executor import LiveExecutor
    from weexbot.weex import RestWeexClient
    from weexbot.weex.rest import WeexAPIError

    signal = parse(args.text)
    print(f"Signal: kind={signal.kind.value} pair={signal.pair} side="
          f"{signal.side.value if signal.side else None} status={signal.status.value}")

    client = RestWeexClient.from_env()
    ex = LiveExecutor(client)
    plan = ex.plan(signal)
    show_plan(plan)
    if not plan.ok:
        return 1
    if plan.notional > args.max_notional:
        print(f"\nODBIJENO: notional {plan.notional:.2f} > cap {args.max_notional} "
              f"(podigni --max-notional ako namjerno).")
        return 1
    if not args.yes:
        print("\nNije proslijedjen --yes. NISTA nije poslano.")
        return 0

    coid = f"sig{int(time.time())}"
    try:
        if not plan.in_band:
            if not args.wait:
                print("\nEntry je izvan +-1% banda. Dodaj --wait da pricekam da udje.")
                return 0
            deadline = time.time() + args.timeout
            print(f"\nCekam da entry udje u bend (poll {args.poll}s, timeout {args.timeout}s)...")
            while time.time() < deadline:
                time.sleep(args.poll)
                plan = ex.plan(signal)               # ponovni izracun s novom cijenom
                print(f"  mark={plan.mark}  in_band={plan.in_band}")
                if plan.ok and plan.in_band:
                    break
            if not (plan.ok and plan.in_band):
                print("Isteklo cekanje, entry nije usao u bend. NISTA nije poslano.")
                return 0

        print("\nPlasiram (set leverage + entry limit + preset SL/TP)...")
        res = ex.place(plan, client_order_id=coid)
        print(f"  -> {res.status}: {res.message[:400]}")
        print("\nProvjera otvorenih naloga:")
        for o in client.open_orders(plan.symbol):
            print("  ", o.message[:300])
    except WeexAPIError as e:
        print(f"\nWEEX greska: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
