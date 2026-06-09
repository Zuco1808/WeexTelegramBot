# -*- coding: utf-8 -*-
"""Testovi gradnje paper naloga."""
from weexbot import parse
from weexbot.paper_broker import build_orders
from weexbot.risk import plan_position


def _orders_for(text):
    s = parse(text)
    plan = plan_position(s.entry, s.stop, s.leverage, capital=100, risk_pct=0.01)
    return s, build_orders(s, plan, "ETHUSDT", key="msgX")


def test_long_nalozi():
    s, orders = _orders_for("$ETHUSDTlongentry - 2739.56; stop - 2632.84take - 2825.47; leverage - x11")
    by_type = {o.otype: o for o in orders}
    assert by_type["ENTRY_LIMIT"].side == "BUY"
    assert by_type["ENTRY_LIMIT"].reduce_only is False
    assert by_type["STOP_LOSS"].side == "SELL"
    assert by_type["STOP_LOSS"].reduce_only is True
    assert by_type["TAKE_PROFIT"].side == "SELL"
    assert by_type["TAKE_PROFIT"].reduce_only is True
    # cijene
    assert by_type["ENTRY_LIMIT"].price == 2739.56
    assert by_type["STOP_LOSS"].price == 2632.84
    assert by_type["TAKE_PROFIT"].price == 2825.47


def test_short_nalozi_obrnute_strane():
    s, orders = _orders_for("ETHUSDT 15mShortPrice: 2060.5TP2: 1932.92SL: 2195.0")
    by_type = {o.otype: o for o in orders}
    assert by_type["ENTRY_LIMIT"].side == "SELL"
    assert by_type["STOP_LOSS"].side == "BUY"
    assert by_type["TAKE_PROFIT"].side == "BUY"


def test_client_order_id_idempotentan():
    _s, orders = _orders_for("$ETHUSDTlongentry - 2739.56; stop - 2632.84take - 2825.47; leverage - x11")
    ids = {o.client_order_id for o in orders}
    assert ids == {"msgX-ENTRY", "msgX-SL", "msgX-TP1"}
