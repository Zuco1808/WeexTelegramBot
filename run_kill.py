"""Kill-switch (Faza 3.7): zaustavi/odmrzni slanje naloga; opc. otkazi otvorene.

    python run_kill.py --status
    python run_kill.py --on "razlog"          # ukljuci (blokira sve naloge)
    python run_kill.py --on "panic" --cancel --symbols BTCUSDT,ETHUSDT
    python run_kill.py --off                   # iskljuci
"""
import argparse
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
KILL_PATH = os.path.join(ROOT, "data", "KILL")


def load_env(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def cancel_open(symbols):
    from weexbot.weex import RestWeexClient
    from weexbot.weex.rest import WeexAPIError
    c = RestWeexClient.from_env()
    for s in symbols:
        try:
            orders = c.open_orders(s)
            for o in orders:
                if o.client_order_id:
                    c.cancel_order(o.client_order_id, s)
            print(f"  {s}: otkazano {len(orders)} naloga")
        except WeexAPIError as e:
            print(f"  {s}: GRESKA {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--on", nargs="?", const="manual", help="ukljuci kill (opc. razlog)")
    ap.add_argument("--off", action="store_true", help="iskljuci kill")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--cancel", action="store_true", help="otkazi otvorene naloge (uz --on)")
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(KILL_PATH), exist_ok=True)
    from weexbot.safety import clear_kill, engage_kill, kill_active

    if args.off:
        print("Kill iskljucen." if clear_kill(KILL_PATH) else "Kill nije ni bio aktivan.")
        return 0

    if args.on is not None:
        engage_kill(KILL_PATH, args.on)
        print(f"KILL UKLJUCEN ({args.on}). Svi novi nalozi blokirani.")
        load_env(os.path.join(ROOT, ".env"))
        from weexbot.notify import notifier_from_env
        notifier_from_env().send(f"⛔ KILL-SWITCH UKLJUCEN: {args.on}")
        if args.cancel:
            print("Otkazivanje otvorenih naloga:")
            cancel_open([s.strip() for s in args.symbols.split(",") if s.strip()])
        return 0

    # default/status
    print(f"Kill-switch: {'AKTIVAN' if kill_active(KILL_PATH) else 'neaktivan'}  ({KILL_PATH})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
