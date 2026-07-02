# -*- coding: utf-8 -*-
"""Testovi klasifikacije nad cijelim korpusom od 50 uzoraka."""
import pytest

from weexbot import classify, normalize
from tests.samples import SAMPLES


@pytest.mark.parametrize("msg_id,text,expected_kind", SAMPLES,
                         ids=[f"msg{s[0]}" for s in SAMPLES])
def test_klasifikacija_korpusa(msg_id, text, expected_kind):
    got = classify(normalize(text)).value
    assert got == expected_kind, (
        f"Poruka {msg_id}: ocekivano {expected_kind}, dobiveno {got}\n  -> {text[:80]!r}"
    )


def test_close_procenat_je_update():
    # "Insiders scalp" salje djelomicno zatvaranje: "BTC / Close 35%" -> E_update,
    # da dodje do Trade Managera (PARTIAL_CLOSE), a ne da bude IGNORED.
    assert classify(normalize("BTC\n\nClose 35%")).value == "E_update"
    assert classify(normalize("HYPE\n\nClose 30%")).value == "E_update"
    assert classify(normalize("BTC\n\nClose 50% of remaining position")).value == "E_update"


def test_close_bez_procenta_ostaje_unknown():
    # "close" u prozi bez postotka nije management -> ne smije postati E.
    assert classify(normalize("We are close to the target")).value == "UNKNOWN"
    assert classify(normalize("Congratulations with great trade")).value == "UNKNOWN"
