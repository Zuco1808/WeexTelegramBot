# -*- coding: utf-8 -*-
"""Testovi REST klijenta - validacija kljuceva, potpis, write-stubovi.

Bez mrežnih poziva (read-only metode se testiraju uživo preko run_live_check.py).
"""
import base64

import pytest

from weexbot.weex import OrderRequest, RestWeexClient
from weexbot.weex.client import ENTRY_LIMIT


def _client():
    return RestWeexClient("key", "secret", "pass", "https://example")


def test_bez_kljuceva_baca_value_error():
    with pytest.raises(ValueError):
        RestWeexClient("", "", "", "https://example")


def test_bez_passphrase_baca_value_error():
    with pytest.raises(ValueError):
        RestWeexClient("key", "secret", "", "https://example")


def test_bez_base_url_baca_value_error():
    with pytest.raises(ValueError):
        RestWeexClient("key", "secret", "pass", "")


def test_sign_je_deterministican_base64():
    c = _client()
    s1 = c._sign("1700000000000", "GET", "/capi/v2/market/time")
    s2 = c._sign("1700000000000", "GET", "/capi/v2/market/time")
    assert s1 == s2
    # validan base64 (HMAC-SHA256 = 32 bajta -> 44 znaka base64)
    assert len(base64.b64decode(s1)) == 32


def test_sign_se_mijenja_s_porukom():
    c = _client()
    a = c._sign("1700000000000", "GET", "/capi/v2/market/time")
    b = c._sign("1700000000000", "POST", "/capi/v2/order/placeOrder", '{"x":1}')
    assert a != b


def test_v2_symbol_konverzija():
    assert RestWeexClient._v2_symbol("BTCUSDT") == "cmt_btcusdt"
    assert RestWeexClient._v2_symbol("XAUTUSDT") == "cmt_xautusdt"
    assert RestWeexClient._v2_symbol("cmt_btcusdt") == "cmt_btcusdt"   # vec konvertirano


# --- gradnja tijela naloga (bez mreze) -------------------------------------- #
def test_leverage_body_isolated():
    c = _client()
    b = c._leverage_body("BTCUSDT", 10, "isolated")
    assert b == {"symbol": "cmt_btcusdt", "marginMode": 3,
                 "longLeverage": "10", "shortLeverage": "10"}


def test_order_body_long_limit():
    c = _client()
    b = c._order_body(OrderRequest("BTCUSDT", "BUY", ENTRY_LIMIT, 0.0001,
                                   price=63000.0, client_order_id="msg6-ENTRY"))
    assert b["symbol"] == "cmt_btcusdt"
    assert b["type"] == "1"               # open long
    assert b["match_price"] == "0"        # limit
    assert b["price"] == "63000"
    assert b["size"] == "0.0001"
    assert b["marginMode"] == 3
    assert b["client_oid"] == "msg6ENTRY"  # sanitiziran (bez '-')


def test_order_body_type_mapping():
    c = _client()

    def typ(side, reduce):
        return c._order_body(OrderRequest("BTCUSDT", side, "TAKE_PROFIT", 0.0001,
                                          price=1.0, reduce_only=reduce))["type"]
    assert typ("BUY", False) == "1"       # open long
    assert typ("SELL", False) == "2"      # open short
    assert typ("SELL", True) == "3"       # close long
    assert typ("BUY", True) == "4"        # close short


def test_order_body_market_nema_price():
    c = _client()
    b = c._order_body(OrderRequest("BTCUSDT", "BUY", "MARKET", 0.0001))
    assert b["match_price"] == "1"
    assert "price" not in b
