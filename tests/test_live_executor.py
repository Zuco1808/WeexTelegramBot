# -*- coding: utf-8 -*-
"""Testovi LiveExecutor-a (FakeClient, bez mreze)."""
from weexbot import parse
from weexbot.live_executor import LiveExecutor
from weexbot.weex import OrderResult

_SPEC = {
    "pricePrecision": 1, "quantityPrecision": 4, "minOrderSize": 0.0001,
    "maxOrderSize": 1200, "contractVal": 0.0001,
    "buyLimitPriceRatio": 0.01, "sellLimitPriceRatio": 0.01,
}


class FakeClient:
    def __init__(self, mark, balance=92.0, spec=None):
        self._mark = mark
        self._balance = balance
        self._spec = spec or dict(_SPEC)
        self.placed = []
        self.leverage_call = None

    def mark_price(self, symbol):
        return self._mark

    def account_balance(self, coin="USDT"):
        return self._balance

    def symbol_spec(self, symbol):
        return self._spec

    def set_leverage(self, symbol, leverage, margin_mode):
        self.leverage_call = (symbol, leverage, margin_mode)
        return {"code": "200"}

    def place_order(self, req):
        self.placed.append(req)
        return OrderResult(req.client_order_id or "x", "SUBMITTED")


_ETH = "$ETHUSDTlongentry - 2739.56; stop - 2632.84take - 2825.47; leverage - x11"


def test_plan_long_sizing_i_zaokruzivanje():
    ex = LiveExecutor(FakeClient(mark=2740.0, balance=92.0))
    p = ex.plan(parse(_ETH))
    assert p.ok and p.side == "BUY"
    assert p.leverage == 10.0                       # x11 clampan na cap 10
    assert p.entry == 2739.6 and p.stop == 2632.8 and p.take_profit == 2825.5
    # rizik 2% * 92 = 1.84; dist=106.72; qty=floor(0.01724,4)=0.0172
    assert p.risk_usdt == 92.0 * 0.02
    assert p.quantity == 0.0172
    assert p.in_band is True


def test_plan_izvan_banda_je_pending():
    ex = LiveExecutor(FakeClient(mark=3000.0))           # >1% od entry 2739.6
    p = ex.plan(parse(_ETH))
    assert p.ok is True and p.in_band is False           # valjan ali ceka bend


def test_plan_qty_ispod_min_se_odbija():
    spec = dict(_SPEC, minOrderSize=1.0)                 # nerealno visok min
    ex = LiveExecutor(FakeClient(mark=2740.0, spec=spec))
    p = ex.plan(parse(_ETH))
    assert p.ok is False and "min" in p.reason.lower()


def test_plan_netradeabilan_signal():
    ex = LiveExecutor(FakeClient(mark=100.0))
    p = ex.plan(parse("Move SL to 68500"))               # update, ne TRADABLE
    assert p.ok is False


def test_place_postavlja_leverage_i_preset_sl_tp():
    fc = FakeClient(mark=2740.0)
    ex = LiveExecutor(fc)
    p = ex.plan(parse(_ETH))
    ex.place(p, client_order_id="t1")
    assert fc.leverage_call == ("ETHUSDT", 10.0, "isolated")
    req = fc.placed[0]
    assert req.side == "BUY" and req.price == 2739.6
    assert req.preset_sl == 2632.8 and req.preset_tp == 2825.5
    assert req.quantity == 0.0172


def test_short_strana():
    ex = LiveExecutor(FakeClient(mark=2060.0))
    p = ex.plan(parse("ETHUSDT 15mShortPrice: 2060.5TP2: 1932.92SL: 2195.0"))
    assert p.ok and p.side == "SELL"
    assert p.stop == 2195.0                              # SL iznad za short
