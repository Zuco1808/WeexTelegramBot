# -*- coding: utf-8 -*-
"""Testovi normalizacije teksta."""
from weexbot import normalize


def test_en_dash_postaje_hyphen():
    assert normalize("4750–4850") == "4750-4850"


def test_tisucice_se_uklanjaju():
    assert normalize("70,000-77,000") == "70000-77000"
    assert normalize("SL = 4,880") == "SL = 4880"


def test_decimalni_zarez_ostaje():
    # 0,3% je decimalni zarez (1 znamenka iza), ne tisucica -> ne diramo
    assert "0,3%" in normalize("Risk: 0,3% / 0.7%")


def test_emoji_se_uklanja_i_ne_lijepi_rijeci():
    out = normalize("\U0001F4C9 ATOM/SHORT")
    assert "ATOM/SHORT" in out
    assert "\U0001F4C9" not in out


def test_visestruke_praznine_kolabiraju():
    assert normalize("a   b\n\nc") == "a b c"


def test_none_vraca_prazan_string():
    assert normalize(None) == ""
