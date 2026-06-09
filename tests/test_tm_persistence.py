# -*- coding: utf-8 -*-
"""Trade Manager + SQLite perzistencija."""
import json

from weexbot import Database, TradeManager


def test_akcije_i_pozicije_se_perzistiraju():
    db = Database(":memory:")
    tm = TradeManager(db=db)
    tm.process("m1", "BTC Short here")
    tm.process("m2", "BTC / Entry 64400-65000 / Stop 65600 / Target 62000")
    tm.process("m3", "BTC Stop to 66100")

    # akcije: OPEN (m2) + MOVE_SL (m3)
    counts = db.tm_action_counts()
    assert counts.get("OPEN") == 1
    assert counts.get("MOVE_SL") == 1

    rows = db.tm_positions()
    assert len(rows) == 1
    btc = rows[0]
    assert btc["pair"] == "BTC"
    assert btc["side"] == "SHORT"
    assert btc["stop"] == 66100.0           # azurirano nakon MOVE_SL
    assert btc["status"] == "OPEN"
    assert json.loads(btc["targets"]) == [62000.0]


def test_upsert_ne_duplicira_par():
    db = Database(":memory:")
    tm = TradeManager(db=db)
    tm.process("m1", "ETH Long")
    tm.process("m2", "ETH / Entry 2000 / Stop 1950")
    tm.process("m3", "ETH Stop to 1980")
    tm.process("m4", "ETH SL to breakeven")
    assert len(db.tm_positions()) == 1       # i dalje samo ETH
    assert db.tm_positions()[0]["stop"] == 2000.0


def test_bez_db_radi_normalno():
    tm = TradeManager()                      # db=None
    a = tm.process("m1", "BTC Long")
    assert a == []                           # nepotpun nacrt, bez greske
