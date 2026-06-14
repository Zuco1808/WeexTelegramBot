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


def test_write_metode_su_stubovi():
    c = _client()
    with pytest.raises(NotImplementedError):
        c.place_order(OrderRequest("BTCUSDT", "BUY", ENTRY_LIMIT, 0.001, price=60000))
    with pytest.raises(NotImplementedError):
        c.set_leverage("BTCUSDT", 5)
    with pytest.raises(NotImplementedError):
        c.cancel_order("x")


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
