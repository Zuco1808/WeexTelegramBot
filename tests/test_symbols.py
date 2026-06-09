# -*- coding: utf-8 -*-
"""Testovi mapiranja/validacije simbola."""
from weexbot import resolve_symbol


def test_kripto_je_tradable():
    assert resolve_symbol("BTCUSDT").tradable is True
    assert resolve_symbol("XMRUSDT").tradable is True


def test_metal_nije_tradable():
    info = resolve_symbol("XAUT")
    assert info.tradable is False
    assert "Metal" in info.reason


def test_tradfi_nije_tradable():
    info = resolve_symbol("PLTR")
    assert info.tradable is False
    assert "TradFi" in info.reason


def test_nepoznat_format_nije_tradable():
    assert resolve_symbol("BTC").tradable is False        # nema USDT sufiks
