# -*- coding: utf-8 -*-
"""Testovi REST skeletona - validacija kljuceva i jasni NotImplementedError."""
import pytest

from weexbot.weex import OrderRequest, RestWeexClient
from weexbot.weex.client import ENTRY_LIMIT


def test_bez_kljuceva_baca_value_error():
    with pytest.raises(ValueError):
        RestWeexClient("", "", "https://example")


def test_bez_base_url_baca_value_error():
    with pytest.raises(ValueError):
        RestWeexClient("key", "secret", "")


def test_metode_su_stubovi():
    c = RestWeexClient("key", "secret", "https://example")
    with pytest.raises(NotImplementedError):
        c.place_order(OrderRequest("BTCUSDT", "BUY", ENTRY_LIMIT, 0.001, price=60000))
    with pytest.raises(NotImplementedError):
        c.positions()
    with pytest.raises(NotImplementedError):
        c.set_leverage("BTCUSDT", 5)


def test_sign_je_deterministican_hex():
    c = RestWeexClient("key", "secret", "https://example")
    s1 = c._sign("payload", "1700000000000")
    s2 = c._sign("payload", "1700000000000")
    assert s1 == s2
    assert len(s1) == 64                       # SHA256 hex
