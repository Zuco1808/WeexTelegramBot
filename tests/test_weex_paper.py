# -*- coding: utf-8 -*-
"""Testovi PaperWeexClient - fill-ovi na temelju cijene."""
import pytest

from weexbot.weex import OrderRequest, PaperWeexClient
from weexbot.weex.client import ENTRY_LIMIT, STOP_LOSS, TAKE_PROFIT


def _client():
    c = PaperWeexClient(balance=100.0)
    c.set_leverage("ETHUSDT", 10)
    return c


def test_set_leverage():
    c = _client()
    assert c.leverage["ETHUSDT"] == 10
    assert c.margin_mode["ETHUSDT"] == "isolated"


def test_limit_entry_fill_long():
    c = _client()
    r = c.place_order(OrderRequest("ETHUSDT", "BUY", ENTRY_LIMIT, 0.01, price=2700))
    assert r.status == "WORKING"
    filled = c.feed_price("ETHUSDT", 2700)
    assert len(filled) == 1
    pos = c.positions()[0]
    assert pos.side == "LONG"
    assert pos.quantity == 0.01
    assert pos.entry_price == 2700


def test_stop_loss_zatvara_long():
    c = _client()
    c.place_order(OrderRequest("ETHUSDT", "BUY", ENTRY_LIMIT, 0.01, price=2700))
    c.feed_price("ETHUSDT", 2700)
    c.place_order(OrderRequest("ETHUSDT", "SELL", STOP_LOSS, 0.01, price=2600, reduce_only=True))
    c.feed_price("ETHUSDT", 2600)
    assert c.positions() == []
    assert c.balance == pytest.approx(100 + 0.01 * (2600 - 2700))   # = 99.0


def test_take_profit_zatvara_short():
    c = _client()
    c.place_order(OrderRequest("ETHUSDT", "SELL", ENTRY_LIMIT, 0.01, price=2000))
    c.feed_price("ETHUSDT", 2000)
    assert c.positions()[0].side == "SHORT"
    c.place_order(OrderRequest("ETHUSDT", "BUY", TAKE_PROFIT, 0.01, price=1900, reduce_only=True))
    c.feed_price("ETHUSDT", 1900)
    assert c.positions() == []
    assert c.balance == pytest.approx(100 + 0.01 * (2000 - 1900))   # short profit = 101.0


def test_oco_sl_se_otkazuje_kad_tp_napuni():
    c = _client()
    c.place_order(OrderRequest("ETHUSDT", "BUY", ENTRY_LIMIT, 0.01, price=2700))
    c.feed_price("ETHUSDT", 2700)
    c.place_order(OrderRequest("ETHUSDT", "SELL", STOP_LOSS, 0.01, price=2600,
                               reduce_only=True, client_order_id="SL1"))
    c.place_order(OrderRequest("ETHUSDT", "SELL", TAKE_PROFIT, 0.01, price=2800,
                               reduce_only=True, client_order_id="TP1"))
    c.feed_price("ETHUSDT", 2800)               # TP puni
    assert c.positions() == []
    assert c.open_orders() == []                # SL otkazan (OCO)


def test_market_fill_na_zadnjoj_cijeni():
    c = _client()
    c.feed_price("ETHUSDT", 2500)               # postavi zadnju cijenu
    r = c.place_order(OrderRequest("ETHUSDT", "BUY", "MARKET", 0.02))
    assert r.status == "FILLED"
    assert c.positions()[0].entry_price == 2500
