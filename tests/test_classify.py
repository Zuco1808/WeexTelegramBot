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
