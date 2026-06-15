"""Faza 3.3 - reconciliation: zatvoreni nalozi s WEEX-a -> trades ledger.

Cita order history, biljezi realizirani PnL zatvorenih trejdova u data/weex_live.db
(dedup po order_id). Potom: python run_reports.py --db weex_live.db  -> pravi PnL.

    python run_reconcile.py                       # jednom, default simboli
    python run_reconcile.py --symbols BTCUSDT,ETHUSDT
    python run_reconcile.py --loop --interval 300 # svakih 5 min (dashboard svjez)
    python run_reconcile.py --debug               # ispisi sirovi history
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

DB_PATH = os.path.join(ROOT, "data", "weex_live.db")
DEFAULT_SYMBOLS = "BTCUSDT,ETHUSDT,SOLUSDT,XAUTUSDT"


def load_env(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=DEFAULT_SYMBOLS)
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--loop", action="store_true", help="ponavljaj zauvijek (za VPS/servis)")
    ap.add_argument("--interval", type=int, default=300, help="razmak u sekundama (uz --loop)")
    args = ap.parse_args()

    load_env(os.path.join(ROOT, ".env"))
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    from weexbot import Database
    from weexbot.reconciler import Reconciler
    from weexbot.weex import RestWeexClient
    from weexbot.weex.rest import WeexAPIError

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    client = RestWeexClient.from_env()
    db = Database(DB_PATH)
    rec = Reconciler(client, db)

    if args.debug:
        for s in symbols:
            try:
                print(f"\n=== history {s} ===")
                print(json.dumps(client.order_history(s), indent=2, ensure_ascii=False)[:1500])
            except WeexAPIError as e:
                print(f"GRESKA {s}: {e}")

    def cycle() -> None:
        try:
            new = rec.reconcile(symbols)
            ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
            print(f"[{ts}] novih: {new}  (ukupno: {db.count('trades')})  -> {DB_PATH}")
        except WeexAPIError as e:
            print(f"WEEX greska: {e}")

    if not args.loop:
        cycle()
        print("Dashboard sa stvarnim PnL:  python run_reports.py --db weex_live.db")
        return 0

    print(f"Auto-reconcile petlja (svakih {args.interval}s). Ctrl+C za prekid.")
    try:
        while True:
            cycle()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nPrekinuto.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
