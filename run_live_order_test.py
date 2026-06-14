"""Faza 3.2 - SIGURAN test pisanja: leverage -> mali limit (ne fila) -> cancel.

Postavlja leverage (isolated, x10), plasira limit BUY ~0.8% ISPOD cijene
(unutar +-1% banda, ispod trzista -> miruje, ne fila se), procita ga, pa ODMAH
otkaze. Velicina = minOrderSize (0.0001 BTC ~ 6.4 USDT notional, marza ~0.64).

Trazi eksplicitni --yes. NE radi market naloge.

    python run_live_order_test.py --yes
    python run_live_order_test.py --yes --symbol BTCUSDT --size 0.0001
"""
import argparse
import json
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

MAX_TEST_SIZE = 0.001          # tvrdi safety cap za ovaj test


def load_env(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def dump(title, obj):
    print(f"\n--- {title} ---")
    print(json.dumps(obj, indent=2, ensure_ascii=False)[:1200])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--size", type=float, default=0.0001)
    ap.add_argument("--leverage", type=int, default=10)
    ap.add_argument("--yes", action="store_true", help="obavezno za stvarno slanje")
    args = ap.parse_args()

    if args.size > MAX_TEST_SIZE:
        print(f"ODBIJENO: size {args.size} > safety cap {MAX_TEST_SIZE}")
        return 1

    load_env(os.path.join(ROOT, ".env"))
    from weexbot.weex import OrderRequest, RestWeexClient
    from weexbot.weex.client import ENTRY_LIMIT
    from weexbot.weex.rest import WeexAPIError

    c = RestWeexClient.from_env()
    mark = c.mark_price(args.symbol)
    if not mark:
        print("Ne mogu dohvatiti cijenu; prekid.")
        return 1
    price = round(mark * 0.992, 1)          # ~0.8% ispod, unutar +-1% banda
    coid = f"wxtest{int(time.time() * 1000)}"
    notional = args.size * mark

    print(f"PLAN (semi-auto test):")
    print(f"  {args.symbol}  leverage x{args.leverage} isolated")
    print(f"  LIMIT BUY  size={args.size}  price={price}  (mark={mark})")
    print(f"  notional ~ {notional:.2f} USDT, marza ~ {notional/args.leverage:.2f} USDT")
    print(f"  client_oid={coid}")
    print("  -> postavi leverage, plasiraj, procitaj, ODMAH otkazi")

    if not args.yes:
        print("\nNije proslijedjen --yes. NISTA nije poslano. Dodaj --yes za stvarni test.")
        return 0

    try:
        dump("set_leverage", c.set_leverage(args.symbol, args.leverage, "isolated"))
        req = OrderRequest(args.symbol, "BUY", ENTRY_LIMIT, args.size,
                           price=price, client_order_id=coid)
        res = c.place_order(req)
        print(f"\nplace_order -> {res.status}: {res.message[:500]}")
        time.sleep(1)
        dump("open_orders (nakon plasiranja)", [o.__dict__ for o in c.open_orders(args.symbol)])
        dump("cancel_order", json.loads(c.cancel_order(coid, args.symbol).message))
        time.sleep(1)
        dump("open_orders (nakon otkazivanja)", [o.__dict__ for o in c.open_orders(args.symbol)])
        dump("assets", c.account_assets())
        print("\nGOTOVO. Ako je nalog plasiran pa otkazan i pozicije su prazne -> 3.2 radi.")
    except WeexAPIError as e:
        print(f"\nWEEX greska: {e}")
        print("Posalji ovu poruku - po kodu cemo tocno vidjeti sto treba (params/precision).")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
