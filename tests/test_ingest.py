# -*- coding: utf-8 -*-
"""Testovi SignalRoutera (cista logika; FakeExecutor, bez mreze/telethona)."""
from weexbot import Database, TradeManager
from weexbot.ingest import SignalRouter
from weexbot.live_executor import OrderPlan

_JEFFREY = "$ETHUSDTlongentry - 2739.56; stop - 2632.84take - 2825.47; leverage - x11"


class FakeExecutor:
    def __init__(self, ok=True, in_band=True):
        self._plan = OrderPlan(ok=ok, reason="OK", symbol="ETHUSDT", side="BUY",
                               quantity=0.0172, entry=2739.6, stop=2632.8,
                               take_profit=2825.5, leverage=10, in_band=in_band)
        self.placed = []

    def plan(self, signal):
        return self._plan

    def place(self, plan, client_order_id=None):
        self.placed.append((plan, client_order_id))
        class R:
            status = "SUBMITTED"
        return R()


def _router(executor=None, mode="notify"):
    db = Database(":memory:")
    return SignalRouter(db, TradeManager(), executor=executor, mode=mode), db


def test_tradable_semi_auto_notify_ne_salje():
    fe = FakeExecutor()
    r, db = _router(fe, mode="notify")
    res = r.handle("m1", _JEFFREY)
    assert res.action == "NOTIFY"
    assert fe.placed == []                    # semi-auto: nista nije poslano
    assert db.signal_exists("m1")


def test_tradable_auto_in_band_salje():
    fe = FakeExecutor(in_band=True)
    r, _ = _router(fe, mode="auto")
    res = r.handle("m1", _JEFFREY)
    assert res.action == "PLACED"
    assert len(fe.placed) == 1


def test_auto_izvan_banda_ne_salje():
    fe = FakeExecutor(in_band=False)
    r, _ = _router(fe, mode="auto")
    res = r.handle("m1", _JEFFREY)
    assert res.action == "NOTIFY"             # izvan banda -> ne salje ni u auto
    assert fe.placed == []


def test_plan_rejected_se_ne_salje():
    fe = FakeExecutor(ok=False)
    r, _ = _router(fe, mode="auto")
    assert r.handle("m1", _JEFFREY).action == "PLAN_REJECTED"
    assert fe.placed == []


def test_dedup_po_message_id():
    r, _ = _router(FakeExecutor())
    assert r.handle("m1", _JEFFREY).action == "NOTIFY"
    assert r.handle("m1", _JEFFREY).action == "DUPLICATE"


def test_chatter_se_ignorira_i_ne_sprema():
    r, db = _router(FakeExecutor())
    res = r.handle("m1", "Had a nice pump, waiting for targets")
    assert res.action == "IGNORED"
    assert db.count("signals") == 0


def test_brandon_d_ide_u_trade_manager():
    r, db = _router(FakeExecutor())
    res = r.handle("m1", "BTC Short here\nEntry: 64000-65000\nStop 66000")
    assert res.action == "TRACKED"
    assert "OPEN" in res.detail["tm"]


def test_tradable_bez_executora():
    r, _ = _router(executor=None)
    assert r.handle("m1", _JEFFREY).action == "TRADABLE_NOEXEC"
