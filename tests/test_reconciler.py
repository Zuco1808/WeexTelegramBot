# -*- coding: utf-8 -*-
"""Testovi Reconilera - order history -> trades ledger (dedup)."""
from weexbot import Database
from weexbot.reconciler import Reconciler

_HIST = [
    {"order_id": "1", "type": "close_long", "filled_qty": "0.001",
     "totalProfits": "5.5", "price_avg": "65000", "createTime": "1781400000000"},
    {"order_id": "9", "type": "open_long", "filled_qty": "0.001",     # ulaz -> ignorira se
     "totalProfits": "0", "price_avg": "64000", "createTime": "1781400000000"},
    {"order_id": "8", "type": "close_short", "filled_qty": "0",       # nije izvrsen
     "totalProfits": "0", "createTime": "1781400000000"},
    {"order_id": "2", "type": "close_short", "filled_qty": "0.002",
     "totalProfits": "-2.0", "price_avg": "63000", "createTime": "1781400500000"},
]


class FakeHistClient:
    def __init__(self, rows):
        self._rows = rows

    def order_history(self, symbol, page_size=100):
        return {"data": {"list": self._rows}}


def test_reconcile_biljezi_samo_filled_close():
    db = Database(":memory:")
    r = Reconciler(FakeHistClient(_HIST), db)
    n = r.reconcile(["BTCUSDT"])
    assert n == 2                                  # samo 2 filled close naloga
    rows = db.trades()
    pnls = sorted(t["pnl"] for t in rows)
    assert pnls == [-2.0, 5.5]
    sides = {t["ext_id"]: t["side"] for t in rows}
    assert sides["1"] == "LONG" and sides["2"] == "SHORT"


def test_reconcile_dedup_drugi_prolaz_nista():
    db = Database(":memory:")
    r = Reconciler(FakeHistClient(_HIST), db)
    assert r.reconcile(["BTCUSDT"]) == 2
    assert r.reconcile(["BTCUSDT"]) == 0           # dedup po ext_id
    assert len(db.trades()) == 2


def test_reconcile_pnl_u_dashboardu():
    from weexbot.reports import summary, trades_from_rows
    db = Database(":memory:")
    Reconciler(FakeHistClient(_HIST), db).reconcile(["BTCUSDT"])
    s = summary(trades_from_rows(db.trades()))
    assert s["total_pnl"] == 3.5                   # 5.5 - 2.0
    assert s["count"] == 2
