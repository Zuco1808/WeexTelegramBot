# -*- coding: utf-8 -*-
"""Testovi ekstrakcije cinjenica iz pojedine poruke (manual_parser)."""
from weexbot.manual_parser import extract_facts


def test_full_setup_jedna_poruka():
    f = extract_facts("BTC / Entry 64400-65000 / Stop 65600 / Target 62000")
    assert f.pairs == ["BTC"]
    assert f.entry_zone == (64400.0, 65000.0)
    assert f.stop_value == 65600.0
    assert f.stop_is_move is False
    assert f.targets == [62000.0]
    assert f.is_building is True


def test_hype_manual_setup_prepoznaje_par():
    # Drugi kanal salje plain-text manual format s vodecim tickerom bez USDT.
    f = extract_facts("HYPE Long\nEntry: 61.2-64.1\nSL: 59.3\nTarget: 74.2")
    assert f.pairs == ["HYPE"]
    assert f.side == "LONG"
    assert f.entry_zone == (61.2, 64.1)
    assert f.stop_value == 59.3
    assert f.targets == [74.2]
    assert f.is_building is True


def test_stop_to_je_move():
    f = extract_facts("BTC Stop to 66100")
    assert f.pairs == ["BTC"]
    assert f.stop_value == 66100.0
    assert f.stop_is_move is True
    assert f.is_building is False
    assert f.has_update is True


def test_breakeven_s_parom():
    f = extract_facts("ETH\n\nSL to breakeven")
    assert f.pairs == ["ETH"]
    assert f.breakeven is True


def test_dva_para_partial_i_breakeven():
    f = extract_facts("BTC ETH\n\nClose 30% of both positions and SL to breakeven")
    assert set(f.pairs) == {"BTC", "ETH"}
    assert f.partial_pct == 30
    assert f.breakeven is True


def test_move_sl_bez_para():
    f = extract_facts("Move SL to 64700")
    assert f.pairs == []
    assert f.stop_value == 64700.0
    assert f.stop_is_move is True


def test_decimalni_zarez_u_sl():
    f = extract_facts("SL - 1,4972")
    assert f.stop_value == 1.4972
    assert f.stop_is_move is True


def test_manual_long_s_targetima_i_dolar():
    f = extract_facts("ASTER | LONG\nEntry: 0,7112 / 0,7043$\nTargets: 0.73 / 0.743 / 0.753$\nSL: 0.6951$")
    assert f.pairs == ["ASTER"]
    assert f.side == "LONG"
    assert f.entry_zone == (0.7112, 0.7043)
    assert f.stop_value == 0.6951
    assert f.targets == [0.73, 0.743, 0.753]


def test_trying_short_s_kontekstom():
    f = extract_facts("Trying another short on BTC from current levels.\n\nStop at 70,700.")
    assert f.pairs == ["BTC"]
    assert f.side == "SHORT"
    assert f.open_hint is True
    assert f.stop_value == 70700.0
    assert f.stop_is_move is False        # "at" nije move


def test_partial_pct_prije_kljucne_rijeci():
    assert extract_facts("50% take here").partial_pct == 50
    assert extract_facts("Take 25% here").partial_pct == 25


def test_numerirani_tp_prefiks():
    # XMR stil: "1TP - 311  2TP - 330  3TP - 347"
    f = extract_facts("XMR Long\nEntry: 289-296\nSL: 283\n1TP - 311\n2TP - 330\n3TP - 347")
    assert f.pairs == ["XMR"]
    assert f.entry_zone == (289.0, 296.0)
    assert f.stop_value == 283.0
    assert f.targets == [311.0, 330.0, 347.0]


def test_numerirani_tp_sufiks_s_instrukcijom():
    # OIL stil: "TP1: 96 - take 50% ... TP2: 117 - close the rest"
    f = extract_facts("Entry: 87\nSecond entry: 82\nTP1: 96 - take 50%\nTP2: 117 - close the rest\nSL: 78.8")
    assert f.entry_zone == (87.0, 82.0)
    assert f.stop_value == 78.8
    assert f.targets == [96.0, 117.0]


def test_label_target_i_dalje_radi():
    assert extract_facts("BTC Short\nEntry: 62200-64300\nSL: 66300\nTarget: 55000").targets == [55000.0]


def test_tiered_entry_s_alokacijom():
    # "Entry: 1. 136.5 - 30%  2. 128 - 70%" -> zona (136.5, 128), ne 1.0
    f = extract_facts("PLTR Long\nEntry:\n1. 136.5 - 30%\n2. 128 - 70%\nSL: 122\nTarget: 156")
    assert f.entry_zone == (136.5, 128.0)
    assert f.stop_value == 122.0
    assert f.targets == [156.0]


def test_tiered_entry_alokacijski_postoci():
    # #3: hvatamo i postotke po ulazu
    f = extract_facts("PLTR Long\nEntry:\n1. 136.5 - 30%\n2. 128 - 70%\nSL: 122\nTarget: 156")
    assert f.entry_tiers == [(136.5, 30), (128.0, 70)]


def test_obican_ulaz_nema_tierova():
    f = extract_facts("BTC Short\nEntry: 62200-64300\nSL: 66300")
    assert f.entry_tiers == []
