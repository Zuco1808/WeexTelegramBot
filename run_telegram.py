"""Faza 3.6 - LIVE Telegram ingest (Telethon) -> SignalRouter.

Slusa kanal, parsira poruke i rutira (A/C semi-auto u izvrsitelj, D/E u Trade
Manager). DEFAULT je semi-auto: javlja plan, NE salje nalog. --auto salje (samo
ako je entry u +-1% bandu).

Preduvjeti (.env):
  TELEGRAM_API_ID, TELEGRAM_API_HASH   (s https://my.telegram.org)
  TELEGRAM_CHANNEL                     (@username, t.me link ili numericki id)
  (opcionalno) WEEX_API_KEY/SECRET/PASSPHRASE -> ukljuci izvrsitelja; inace samo prati

    pip install telethon
    python run_telegram.py                 # semi-auto (samo javlja)
    python run_telegram.py --auto          # auto salje (u bandu)
    python run_telegram.py --backfill 20   # obradi zadnjih 20 poruka na startu
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


def load_env(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def build_executor():
    """LiveExecutor ako su WEEX kljucevi postavljeni; inace None (samo pracenje)."""
    from weexbot.config import weex_credentials
    if not all(weex_credentials()):
        print("(WEEX kljucevi nisu postavljeni -> samo pracenje, bez izvrsitelja)")
        return None
    from weexbot.live_executor import LiveExecutor
    from weexbot.weex import RestWeexClient
    return LiveExecutor(RestWeexClient.from_env())


def on_plan(message_id, signal, plan):
    print("\n  >>> TRADABLE SIGNAL <<<")
    print(f"      {plan.symbol} {plan.side} qty={plan.quantity} @ {plan.entry} "
          f"SL={plan.stop} TP={plan.take_profit} x{plan.leverage:g}")
    print(f"      notional~{plan.notional:.2f} marza~{plan.margin:.2f}  u_bandu={plan.in_band}")
    txt = signal.raw_text.replace('"', "'")[:200]
    print(f"      Za izvrsenje:  python run_live_trade.py --text \"{txt}\" --yes --wait")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--auto", action="store_true", help="auto salji naloge (u bandu)")
    ap.add_argument("--backfill", type=int, default=0, help="obradi zadnjih N poruka na startu")
    args = ap.parse_args()

    load_env(os.path.join(ROOT, ".env"))
    try:
        from telethon import TelegramClient, events
    except ImportError:
        print("Telethon nije instaliran. Pokreni:  pip install telethon")
        return 1

    from weexbot import Database, TradeManager
    from weexbot.config import telegram_config
    from weexbot.ingest import SignalRouter

    api_id, api_hash, channel = telegram_config()
    if not all([api_id, api_hash, channel]):
        print("Nedostaju TELEGRAM_API_ID / TELEGRAM_API_HASH / TELEGRAM_CHANNEL u .env")
        return 1

    from weexbot.notify import notifier_from_env
    from weexbot.safety import SafetyGate
    db = Database(os.path.join(ROOT, "data", "weex_live.db"))
    executor = build_executor()
    count_open = (lambda: len(executor.client.positions())) if executor else None
    gate = SafetyGate(db, os.path.join(ROOT, "data", "KILL"), count_open=count_open)
    notifier = notifier_from_env()
    router = SignalRouter(db, TradeManager(db=db), executor=executor,
                          mode="auto" if args.auto else "notify",
                          on_plan=on_plan, gate=gate, notifier=notifier)
    print(f"Mod: {'AUTO (salje u bandu)' if args.auto else 'SEMI-AUTO (samo javlja)'}  "
          f"(kill-switch + dnevni stop + limit pozicija aktivni)")

    client = TelegramClient(os.path.join(ROOT, "data", "tg_session"), int(api_id), api_hash)

    async def handle_msg(message_id, text, date):
        res = router.handle(message_id, text, date)
        print(f"[{message_id}] {res.action}  {res.detail}")

    @client.on(events.NewMessage(chats=channel))
    async def _on_new(event):
        d = event.message.date.isoformat() if event.message and event.message.date else None
        await handle_msg(str(event.id), event.raw_text or "", d)

    async def run():
        await client.start()
        ent = await client.get_entity(channel)
        print(f"Slusam: {getattr(ent, 'title', channel)}")
        if args.backfill:
            msgs = await client.get_messages(ent, limit=args.backfill)
            for m in reversed(msgs):
                d = m.date.isoformat() if m.date else None
                await handle_msg(str(m.id), m.raw_text or "", d)
        print("Cekam nove poruke... (Ctrl+C za prekid)")
        await client.run_until_disconnected()

    with client:
        client.loop.run_until_complete(run())
    return 0


if __name__ == "__main__":
    sys.exit(main())
