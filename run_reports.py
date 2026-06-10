"""Dashboard / izvjestaji nad trades ledgerom.

Pokretanje:
    python run_reports.py --seed-demo     # napuni DEMO trejdove pa prikazi dashboard
    python run_reports.py                  # prikazi iz postojece baze
    python run_reports.py --html           # izvezi data/report.html

NAPOMENA: pravi PnL po danima dolazi tek s cijenama u Fazi 3 (live/price feed).
Do tada --seed-demo sluzi da vidis format izvjestaja.
"""
import argparse
import os
import random
import sys
from datetime import datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8")     # Windows konzola: omoguci emoji/▁▂▃
except (AttributeError, ValueError):
    pass

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from weexbot import Database                              # noqa: E402
from weexbot.reports import render_dashboard, to_html, trades_from_rows  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.path.join(DATA_DIR, "weex_reports.db")
HTML_PATH = os.path.join(DATA_DIR, "report.html")

_SYMBOLS = ["BTCUSDT", "ETHUSDT", "ASTERUSDT", "XAUTUSDT", "XTIUSDT", "AAPLUSDT"]


def seed_demo(db: Database, n: int = 60, days: int = 42) -> None:
    """Deterministicki DEMO trejdovi (nije pravi PnL)."""
    rng = random.Random(42)
    db.clear_trades()
    start = datetime.now(timezone.utc) - timedelta(days=days)
    for _ in range(n):
        sym = rng.choice(_SYMBOLS)
        side = rng.choice(["LONG", "SHORT"])
        # blagi pozitivni edge da dashboard ima i zelene i crvene
        pnl = round(rng.gauss(0.6, 4.0), 2)
        when = start + timedelta(days=rng.randint(0, days),
                                 hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
        db.record_trade(sym, side, quantity=rng.uniform(0.01, 1.0),
                        entry_price=None, exit_price=None, pnl=pnl,
                        closed_at=when.isoformat(), source="DEMO")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed-demo", action="store_true", help="napuni DEMO trejdove")
    ap.add_argument("--html", action="store_true", help="izvezi data/report.html")
    ap.add_argument("--no-color", action="store_true", help="bez ANSI boja")
    args = ap.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)
    db = Database(DB_PATH)
    if args.seed_demo:
        seed_demo(db)
        print("(napunjeni DEMO trejdovi)\n")

    trades = trades_from_rows(db.trades())
    if not trades:
        print("Nema trejdova u bazi. Pokreni s --seed-demo za demo prikaz,")
        print("ili ce se puniti automatski kad PaperWeexClient(db=...) zatvara pozicije.")
        return 0

    print(render_dashboard(trades, color=not args.no_color))

    if args.html:
        with open(HTML_PATH, "w", encoding="utf-8") as f:
            f.write(to_html(trades))
        print(f"\nHTML izvjestaj: {HTML_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
