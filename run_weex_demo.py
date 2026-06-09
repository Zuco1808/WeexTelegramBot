"""Demo cijelog stoga: signal -> orders -> izvrsenje na PaperWeexClient.

Pokazuje da parse + risk + paper_broker + WEEX paper klijent rade zajedno:
postavi entry/SL/TP, pa "gurni" cijene i gledaj fill-ove i PnL.
(Bez mreze i bez kljuceva.)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from weexbot import parse                                   # noqa: E402
from weexbot.config import CAPITAL_USDT, RISK_PCT_SCALP     # noqa: E402
from weexbot.paper_broker import build_orders               # noqa: E402
from weexbot.risk import plan_position                      # noqa: E402
from weexbot.symbols import resolve_symbol                  # noqa: E402
from weexbot.weex import OrderRequest, PaperWeexClient      # noqa: E402

SIGNAL = "$ETHUSDTlongentry - 2739.56; stop - 2632.84take - 2825.47; leverage - x11"


def main() -> int:
    sig = parse(SIGNAL)
    info = resolve_symbol(sig.pair)
    plan = plan_position(sig.entry, sig.stop, sig.leverage, CAPITAL_USDT, RISK_PCT_SCALP)
    orders = build_orders(sig, plan, info.weex_symbol, key="demo")

    print(f"Signal: {sig.pair} {sig.side.value} entry={sig.entry} stop={sig.stop} "
          f"tp={sig.take_profits[0].price} lev=x{sig.leverage:g}")
    print(f"Sizing (kapital {CAPITAL_USDT:g}, rizik {RISK_PCT_SCALP*100:g}%): "
          f"qty={plan.quantity:.6f}  margina={plan.margin:.2f} USDT\n")

    client = PaperWeexClient(balance=CAPITAL_USDT)
    client.set_leverage(info.weex_symbol, sig.leverage)
    for o in orders:
        r = client.place_order(OrderRequest(
            symbol=o.symbol, side=o.side, otype=o.otype, quantity=o.quantity,
            price=o.price, reduce_only=o.reduce_only, client_order_id=o.client_order_id,
        ))
        print(f"  postavljen {o.otype:12s} {o.side:4s} @ {o.price}  -> {r.status}")

    print("\nScenarij A: cijena dode na ulaz pa na TAKE PROFIT")
    for px in (sig.entry, sig.take_profits[0].price):
        filled = client.feed_price(info.weex_symbol, px)
        for f in filled:
            print(f"  cijena {px:>9.2f} -> FILL {f.client_order_id}")
    print(f"  otvorene pozicije: {len(client.positions())}")
    print(f"  stanje racuna: {client.balance:.4f} USDT "
          f"(PnL {client.balance - CAPITAL_USDT:+.4f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
