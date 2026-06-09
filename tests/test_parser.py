# -*- coding: utf-8 -*-
"""Testovi parsera: ekstrakcija polja (A, C), sigurnost i status."""
import pytest

from weexbot import parse, Side, SignalKind, TradeStatus
from weexbot.risk import plan_position
from tests.samples import SAMPLES, TRADABLE_IDS


# --------------------------------------------------------------------------- #
# NAJVAZNIJI test: nista sto nije precizan A/C signal ne smije biti TRADABLE.
# Ovo je sigurnosna mreza - chatter/update/legenda nikad ne smiju zavrsiti
# kao zivi (paper) nalog.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("msg_id,text,_kind", SAMPLES,
                         ids=[f"msg{s[0]}" for s in SAMPLES])
def test_samo_dozvoljeni_idevi_su_tradable(msg_id, text, _kind):
    sig = parse(text)
    if msg_id in TRADABLE_IDS:
        assert sig.is_tradable, f"Poruka {msg_id} bi trebala biti TRADABLE"
    else:
        assert not sig.is_tradable, (
            f"SIGURNOST: poruka {msg_id} NE SMIJE biti TRADABLE ({_kind})"
        )


# --------------------------------------------------------------------------- #
# Format A (Jeffrey) - tocna ekstrakcija polja + leverage cap
# --------------------------------------------------------------------------- #
def test_format_a_polja():
    s = parse("$ETHUSDTlongentry - 2739.56; stop - 2632.84take - 2825.47; leverage - x11")
    assert s.kind == SignalKind.JEFFREY
    assert s.pair == "ETHUSDT"
    assert s.side == Side.LONG
    assert s.entry == 2739.56
    assert s.stop == 2632.84
    assert s.take_profits[0].price == 2825.47
    assert s.leverage == 10.0          # x11 clampano na cap 10
    assert s.status == TradeStatus.TRADABLE


def test_format_a_btc():
    s = parse("$BTCUSDTlongentry - 78964.2; stop - 77032.2take - 80522.8; leverage - x17")
    assert (s.pair, s.entry, s.stop) == ("BTCUSDT", 78964.2, 77032.2)
    assert s.leverage == 10.0


# --------------------------------------------------------------------------- #
# Format C (bot) - tocna ekstrakcija, default leverage, timeframe
# --------------------------------------------------------------------------- #
def test_format_c_polja():
    s = parse("BTCUSDT 5mLongPrice: 69432.1TP1: 69814.0SL: 68928.0")
    assert s.kind == SignalKind.BOT
    assert s.pair == "BTCUSDT"
    assert s.side == Side.LONG
    assert s.entry == 69432.1
    assert s.stop == 68928.0
    assert s.take_profits[0].price == 69814.0
    assert s.timeframe == "5m"
    assert s.leverage == 5.0           # bot nema leverage -> default
    assert s.status == TradeStatus.TRADABLE


def test_format_c_short_sanity_ok():
    s = parse("ETHUSDT 15mShortPrice: 2060.5TP2: 1932.92SL: 2195.0")
    assert s.side == Side.SHORT
    assert s.stop > s.entry > s.take_profits[0].price
    assert s.is_tradable


# --------------------------------------------------------------------------- #
# Format B (zona) - metali se preskacu, crypto se parsira ali NE trguje
# --------------------------------------------------------------------------- #
def test_format_b_metal_skipped():
    s = parse("XAUT/SHORT 15-40Entry point: 4,750–4,850TP:4,600 / fix 75%move stop to breakeven4,450 / fix 25%SL = 4,880")
    assert s.kind == SignalKind.ZONE
    assert s.status == TradeStatus.SKIPPED_NO_SYMBOL
    assert s.entry_zone == (4750.0, 4850.0)
    assert s.stop == 4880.0
    assert not s.is_tradable


def test_format_b_crypto_not_traded_phase1():
    s = parse("HBAR/SHORT x11-16Entry point: 0.09100-0.09500TP:0.08750 / fix 75%move stop to breakeven0.08300 / fix 25%SL = 0.09650")
    assert s.kind == SignalKind.ZONE
    assert s.status == TradeStatus.NOT_TRADED_PHASE1
    assert s.leverage == 10.0          # min(11,16) -> 11 clampano na 10
    assert len(s.take_profits) == 2
    assert not s.is_tradable


def test_format_b_multi_tp_s_breakevenom():
    s = parse("BTC/LONG x4-10Entry point: 70,000–77,000TP:82,250 / move stop to breakeven88,000 / fix 50%93,000 / fix 25%move stop to 2nd TP97,950 / fix 25%SL = 69,000")
    cijene = [tp.price for tp in s.take_profits]
    assert cijene == [82250.0, 88000.0, 93000.0, 97950.0]
    assert s.stop == 69000.0
    assert s.leverage == 4.0           # min(4,10) -> 4 (ispod capa)


# --------------------------------------------------------------------------- #
# Update / info / chatter - klasifikacija i status
# --------------------------------------------------------------------------- #
def test_update_move_sl_detektira_vrijednost():
    s = parse("Move SL to 68500")
    assert s.kind == SignalKind.UPDATE
    assert s.status == TradeStatus.NEEDS_REVIEW
    assert any("68500" in n for n in s.notes)


def test_legenda_je_info():
    from tests.samples import SAMPLES as _S
    legenda = _S[0][1]
    s = parse(legenda)
    assert s.kind == SignalKind.INFO
    assert s.status == TradeStatus.INFO


# --------------------------------------------------------------------------- #
# Risk engine - position sizing za 100 USDT / 1%
# --------------------------------------------------------------------------- #
def test_position_sizing():
    # entry 2739.56, stop 2632.84 -> dist 106.72; rizik 1 USDT
    plan = plan_position(entry=2739.56, stop=2632.84, leverage=10, capital=100, risk_pct=0.01)
    assert plan is not None
    assert plan.risk_usdt == pytest.approx(1.0)
    assert plan.quantity == pytest.approx(1.0 / 106.72, rel=1e-6)
    # ako SL bude pogoden, gubitak ~ rizik_usdt
    assert plan.quantity * abs(2739.56 - 2632.84) == pytest.approx(1.0, rel=1e-9)
