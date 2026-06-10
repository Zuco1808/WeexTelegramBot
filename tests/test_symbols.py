# -*- coding: utf-8 -*-
"""Testovi mapiranja/validacije simbola (kripto + TradFi/RWA)."""
from weexbot import resolve_symbol


def test_kripto_je_tradable():
    assert resolve_symbol("BTCUSDT").tradable is True
    assert resolve_symbol("XMRUSDT").tradable is True
    assert resolve_symbol("BTC").weex_symbol == "BTCUSDT"     # bare ime -> +USDT


def test_metali_su_tradable():
    assert resolve_symbol("XAUT").tradable is True
    assert resolve_symbol("XAUT").weex_symbol == "XAUTUSDT"
    assert resolve_symbol("GOLD").weex_symbol == "XAUTUSDT"
    assert resolve_symbol("XAG").weex_symbol == "XAGUSDT"


def test_nafta_i_dionice_tradable():
    assert resolve_symbol("OIL").weex_symbol == "XTIUSDT"     # WTI -> XTI
    assert resolve_symbol("WTI").weex_symbol == "XTIUSDT"
    assert resolve_symbol("AAPL").weex_symbol == "AAPLUSDT"
    assert resolve_symbol("MSFT").weex_symbol == "MSFTUSDT"


def test_on_sufiks_se_mapira_na_usdt():
    assert resolve_symbol("GOOGLON").weex_symbol == "GOOGLUSDT"
    assert resolve_symbol("INTCON").weex_symbol == "INTCUSDT"


def test_nepodrzane_dionice_nisu_tradable():
    info = resolve_symbol("PLTR")
    assert info.tradable is False
    assert "WEEX listi" in info.reason


def test_nepoznat_simbol_nije_tradable():
    assert resolve_symbol("ZZZZ").tradable is False
