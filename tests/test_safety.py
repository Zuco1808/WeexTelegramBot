# -*- coding: utf-8 -*-
"""Testovi sigurnosnog sloja: kill-switch, dnevni stop, limit pozicija."""
from datetime import datetime, timezone

from weexbot import Database
from weexbot.safety import (
    SafetyGate,
    clear_kill,
    daily_realized_pnl,
    engage_kill,
    kill_active,
)


def _kill_path(tmp_path):
    return str(tmp_path / "KILL")


def test_kill_switch_file(tmp_path):
    p = _kill_path(tmp_path)
    assert not kill_active(p)
    engage_kill(p, "test")
    assert kill_active(p)
    assert clear_kill(p) is True
    assert not kill_active(p)


def _today_iso():
    return datetime.now(timezone.utc).isoformat()


def test_daily_realized_pnl_filtrira_izvor_i_dan():
    db = Database(":memory:")
    db.record_trade("BTCUSDT", "LONG", 0.01, None, None, 5.0,
                    closed_at=_today_iso(), source="live")
    db.record_trade("ETHUSDT", "SHORT", 0.1, None, None, -2.0,
                    closed_at=_today_iso(), source="live")
    db.record_trade("BTCUSDT", "LONG", 0.01, None, None, 99.0,
                    closed_at="2020-01-01T00:00:00+00:00", source="live")   # stari dan
    db.record_trade("BTCUSDT", "LONG", 0.01, None, None, 50.0,
                    closed_at=_today_iso(), source="DEMO")                    # drugi izvor
    assert daily_realized_pnl(db) == 3.0           # 5 - 2 (samo live, danas)


def test_gate_blokira_na_kill(tmp_path):
    db = Database(":memory:")
    p = _kill_path(tmp_path)
    engage_kill(p, "x")
    g = SafetyGate(db, p, max_positions=5, daily_loss_limit=5.0, count_open=lambda: 0)
    r = g.check()
    assert r.ok is False and "kill" in r.reason.lower()


def test_gate_blokira_na_dnevni_gubitak(tmp_path):
    db = Database(":memory:")
    db.record_trade("BTCUSDT", "LONG", 0.01, None, None, -6.0,
                    closed_at=_today_iso(), source="live")
    g = SafetyGate(db, _kill_path(tmp_path), daily_loss_limit=5.0, count_open=lambda: 0)
    assert g.check().ok is False


def test_gate_blokira_na_limit_pozicija(tmp_path):
    db = Database(":memory:")
    g = SafetyGate(db, _kill_path(tmp_path), max_positions=2,
                   daily_loss_limit=None, count_open=lambda: 2)
    assert g.check().ok is False


def test_gate_ok_kad_je_sve_uredu(tmp_path):
    db = Database(":memory:")
    g = SafetyGate(db, _kill_path(tmp_path), max_positions=5,
                   daily_loss_limit=5.0, count_open=lambda: 1)
    assert g.check().ok is True
