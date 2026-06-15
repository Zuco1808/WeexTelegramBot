# -*- coding: utf-8 -*-
"""Testovi notifiera (bez mreze) + integracija u router."""
from weexbot import Database, TradeManager
from weexbot.ingest import SignalRouter
from weexbot.live_executor import OrderPlan
from weexbot.notify import NullNotifier, notifier_from_env

_JEFFREY = "$ETHUSDTlongentry - 2739.56; stop - 2632.84take - 2825.47; leverage - x11"


def test_null_notifier_kad_nema_konfiguracije(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_ALERT_CHAT_ID", raising=False)
    assert isinstance(notifier_from_env(), NullNotifier)
    assert notifier_from_env().send("test") is False


def test_telegram_notifier_kad_je_konfiguriran(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_ALERT_CHAT_ID", "999")
    from weexbot.notify import TelegramNotifier
    assert isinstance(notifier_from_env(), TelegramNotifier)


class _FakeExecutor:
    def __init__(self):
        self._plan = OrderPlan(ok=True, reason="OK", symbol="ETHUSDT", side="BUY",
                               quantity=0.0172, entry=2739.6, stop=2632.8,
                               take_profit=2825.5, leverage=10, in_band=True)

    def plan(self, signal):
        return self._plan

    def place(self, plan, client_order_id=None):
        class R:
            status = "SUBMITTED"
        return R()


class _RecordingNotifier(NullNotifier):
    def __init__(self):
        self.sent = []

    def send(self, text):
        self.sent.append(text)
        return True


def test_router_salje_alarm_na_notify():
    n = _RecordingNotifier()
    r = SignalRouter(Database(":memory:"), TradeManager(), executor=_FakeExecutor(),
                     mode="notify", notifier=n)
    r.handle("m1", _JEFFREY)
    assert len(n.sent) == 1 and "SIGNAL" in n.sent[0]


def test_router_salje_alarm_na_placed():
    n = _RecordingNotifier()
    r = SignalRouter(Database(":memory:"), TradeManager(), executor=_FakeExecutor(),
                     mode="auto", notifier=n)
    res = r.handle("m1", _JEFFREY)
    assert res.action == "PLACED"
    assert any("PLASIRANO" in s for s in n.sent)
