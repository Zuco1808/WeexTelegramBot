"""Faza 3.3 - reconciliation: zatvoreni nalozi s WEEX-a -> trades ledger.

Cita order history, biljezi realizirani PnL zatvorenih trejdova u data/weex_live.db
(dedup po order_id). Potom: python run_reports.py --db weex_live.db  -> pravi PnL.

    python run_reconcile.py                       # default simboli
    python run_reconcile.py --symbols BTCUSDT,ETHUSDT
    python run_reconcile.py --debug               # ispisi sirovi history
"""
import argparse
import json
import os
import sys

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

    if args.debug:
        for s in symbols:
            try:
                print(f"\n=== history {s} ===")
                print(json.dumps(client.order_history(s), indent=2, ensure_ascii=False)[:1500])
            except WeexAPIError as e:
                print(f"GRESKA {s}: {e}")

    try:
        new = Reconciler(client, db).reconcile(symbols)
    except WeexAPIError as e:
        print(f"\nWEEX greska: {e}")
        print("Posalji poruku (po polju/kodu doradimo parsiranje history-ja).")
        return 1

    print(f"\nNovih zabiljezenih zatvorenih trejdova: {new}")
    print(f"Ledger: {DB_PATH}  (ukupno trejdova: {db.count('trades')})")
    print("Dashboard sa stvarnim PnL:  python run_reports.py --db weex_live.db")
    return 0


if __name__ == "__main__":
    sys.exit(main())
