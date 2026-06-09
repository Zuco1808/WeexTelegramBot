# -*- coding: utf-8 -*-
"""Testovi SQLite persistencije."""
import pytest

from weexbot import Database, parse


def test_schema_i_account():
    db = Database(":memory:", starting_balance=100.0)
    assert db.balance() == 100.0
    assert db.count("signals") == 0


def test_insert_i_signal_exists():
    db = Database(":memory:")
    sig = parse("$ETHUSDTlongentry - 2739.56; stop - 2632.84take - 2825.47; leverage - x11")
    assert not db.signal_exists("m1")
    db.insert_signal("m1", sig, "2026-02-01")
    assert db.signal_exists("m1")
    assert db.count("signals") == 1


def test_message_id_je_unique():
    db = Database(":memory:")
    sig = parse("$ETHUSDTlongentry - 2739.56; stop - 2632.84take - 2825.47; leverage - x11")
    db.insert_signal("m1", sig)
    with pytest.raises(Exception):
        db.insert_signal("m1", sig)   # UNIQUE constraint


def test_audit_log():
    db = Database(":memory:")
    db.audit("test_event", "m1", {"x": 1})
    assert db.count("audit_log") == 1
