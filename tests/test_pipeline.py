# -*- coding: utf-8 -*-
"""Testovi pipeline-a: persist, idempotentnost, skip simbola, sigurnost."""
from weexbot import Database, Pipeline
from weexbot.risk import plan_position


def _pipe():
    db = Database(":memory:", starting_balance=100.0)
    return db, Pipeline(db, capital=100.0, risk_pct=0.01)


def test_tradable_signal_stvara_poziciju_i_3_naloga():
    db, pipe = _pipe()
    res = pipe.process("m1", "$ETHUSDTlongentry - 2739.56; stop - 2632.84take - 2825.47; leverage - x11")
    assert res.action == "POSITION_PLANNED"
    assert db.count("positions") == 1
    assert db.count("orders") == 3


def test_idempotentnost_nema_duplih_pozicija():
    db, pipe = _pipe()
    text = "$ETHUSDTlongentry - 2739.56; stop - 2632.84take - 2825.47; leverage - x11"
    pipe.process("m1", text)
    res2 = pipe.process("m1", text)             # isti message_id
    assert res2.action == "SKIPPED_DUPLICATE"
    assert db.count("positions") == 1           # i dalje samo jedna
    assert db.count("orders") == 3


def test_update_poruka_ne_stvara_poziciju():
    db, pipe = _pipe()
    res = pipe.process("m1", "Move SL to 68500")
    assert res.action == "STORED"
    assert db.count("positions") == 0
    assert db.count("signals") == 1             # spremljeno za Trade Manager


def test_chatter_se_ignorira():
    db, pipe = _pipe()
    res = pipe.process("m1", "Had a nice pump, waiting for targets")
    assert res.action == "IGNORED"
    assert db.count("signals") == 0


def test_metal_se_preskace():
    db, pipe = _pipe()
    # metal Format B nije ni tradable, ali provjeravamo da ne stvara poziciju
    res = pipe.process("m1", "XAUT/SHORT 15-40Entry point: 4,750-4,850TP:4,600 / fix 75%SL = 4,880")
    assert db.count("positions") == 0
    assert res.action in ("STORED", "SKIPPED_SYMBOL")


def test_limit_broja_otvorenih_pozicija():
    db = Database(":memory:", starting_balance=100.0)
    pipe = Pipeline(db, capital=100.0, risk_pct=0.01, max_open=1)
    r1 = pipe.process("m1", "$ETHUSDTlongentry - 2739.56; stop - 2632.84take - 2825.47; leverage - x11")
    r2 = pipe.process("m2", "$BTCUSDTlongentry - 78964.2; stop - 77032.2take - 80522.8; leverage - x17")
    assert r1.action == "POSITION_PLANNED"
    assert r2.action == "SKIPPED_EXPOSURE"
    assert db.count("positions") == 1


def test_limit_ukupne_margine():
    db = Database(":memory:", starting_balance=100.0)
    # vrlo niska granica margine -> blokira i prvu poziciju
    pipe = Pipeline(db, capital=100.0, risk_pct=0.01, max_open=99, max_margin_pct=0.001)
    r = pipe.process("m1", "$ETHUSDTlongentry - 2739.56; stop - 2632.84take - 2825.47; leverage - x11")
    assert r.action == "SKIPPED_EXPOSURE"
    assert db.count("positions") == 0


def test_position_sizing_zapisan_tocno():
    db, pipe = _pipe()
    pipe.process("m1", "$ETHUSDTlongentry - 2739.56; stop - 2632.84take - 2825.47; leverage - x11")
    p = db.positions()[0]
    expected = plan_position(2739.56, 2632.84, 10, capital=100, risk_pct=0.01)
    assert p["quantity"] == expected.quantity
    assert p["risk_usdt"] == expected.risk_usdt
    assert p["symbol"] == "ETHUSDT"
    assert p["side"] == "LONG"
