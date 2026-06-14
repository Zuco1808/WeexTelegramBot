"""Faza 3.1 - READ-ONLY provjera WEEX API veze (NE šalje naloge).

Pokretanje (ti, sa svojim kljucevima u .env):
    python run_live_check.py
    python run_live_check.py --symbol ETHUSDT

Ucitava .env (WEEX_API_KEY / WEEX_API_SECRET / WEEX_API_PASSPHRASE / WEEX_BASE_URL),
pa: server time -> ticker (javno) -> account assets -> positions (autentificirano).
Ispisuje SIROVI JSON da potvrdimo tocne nazive polja prije Faze 3.2 (pisanje).
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


def load_env(path: str) -> None:
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def show(title, fn):
    print(f"\n=== {title} ===")
    try:
        print(json.dumps(fn(), indent=2, ensure_ascii=False)[:1500])
    except Exception as e:                      # namjerno siroko: dijagnostika veze
        print(f"GRESKA: {e}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTCUSDT")
    args = ap.parse_args()

    load_env(os.path.join(ROOT, ".env"))
    from weexbot.weex import RestWeexClient
    from weexbot.weex.rest import WeexAPIError

    try:
        client = RestWeexClient.from_env()
    except ValueError as e:
        print(f"Kljucevi nisu postavljeni: {e}")
        print("Popuni .env (vidi .env.example) pa pokreni ponovo.")
        return 1

    print(f"Base URL: {client.base_url}  |  API key: ...{client.api_key[-4:]}")
    show("Server time (javno)", client.server_time)
    show(f"Ticker {args.symbol} (javno)", lambda: client.ticker(args.symbol))
    print(f"\nmark_price({args.symbol}) = {client.mark_price(args.symbol)}")
    show("Account assets (auth)", client.account_assets)
    show("Positions (auth)", client.raw_positions)

    print("\nAko su 'auth' sekcije prošle bez greške -> ključevi i potpis rade.")
    print("NE šaljemo naloge u ovom koraku (read-only). Sljedeće: Faza 3.2 (pisanje).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
