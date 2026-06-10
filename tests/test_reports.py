# -*- coding: utf-8 -*-
"""Testovi izvjestaja (agregacije; bez ovisnosti o ANSI bojama)."""
from datetime import datetime

from weexbot import Database
from weexbot.reports import (
    Trade,
    aggregate,
    by_symbol,
    equity_svg,
    render_dashboard,
    summary,
    to_html,
    trades_from_rows,
)


def _t(symbol, pnl, day):
    return Trade(symbol, "LONG", pnl, datetime(2026, 6, day, 12, 0))


def test_dnevna_agregacija_pnl_i_broj():
    trades = [_t("BTCUSDT", 10, 9), _t("ETHUSDT", -4, 9), _t("BTCUSDT", 5, 10)]
    buckets = {b.key: b for b in aggregate(trades, "day")}
    assert buckets["2026-06-09"].pnl == 6        # 10 - 4
    assert buckets["2026-06-09"].count == 2
    assert buckets["2026-06-09"].wins == 1
    assert buckets["2026-06-10"].pnl == 5
    assert buckets["2026-06-10"].count == 1


def test_sedmicna_i_mjesecna():
    trades = [_t("BTCUSDT", 10, 1), _t("BTCUSDT", 20, 8)]   # razlicite sedmice
    assert len(aggregate(trades, "week")) == 2
    assert len(aggregate(trades, "month")) == 1             # isti mjesec


def test_summary_winrate_i_najbolji():
    trades = [_t("BTCUSDT", 10, 9), _t("ETHUSDT", -4, 10), _t("BTCUSDT", 6, 9)]
    s = summary(trades)
    assert s["total_pnl"] == 12
    assert s["count"] == 3
    assert round(s["winrate"]) == 67                         # 2/3
    assert s["best"].key == "2026-06-09"                     # +16
    assert s["worst"].key == "2026-06-10"                    # -4


def test_po_simbolu_sortirano_po_pnl():
    trades = [_t("BTCUSDT", -5, 9), _t("ETHUSDT", 20, 9)]
    bs = by_symbol(trades)
    assert bs[0].key == "ETHUSDT"                             # najveci PnL prvi
    assert bs[0].pnl == 20


def test_prazno_ne_puca():
    assert summary([])["count"] == 0
    assert "IZVJESTAJ" in render_dashboard([], color=False)
    assert equity_svg([]) == ""             # prazno -> nema grafa


def test_equity_svg_i_html_graf():
    trades = [_t("BTCUSDT", 10, 9), _t("ETHUSDT", -4, 10), _t("BTCUSDT", 6, 11)]
    svg = equity_svg(trades)
    assert svg.startswith("<svg") and "polyline" in svg
    html = to_html(trades)
    assert "Equity curve" in html and "<svg" in html


def test_ledger_iz_baze():
    db = Database(":memory:")
    db.record_trade("BTCUSDT", "LONG", 0.01, 100, 110, pnl=1.0,
                    closed_at="2026-06-09T12:00:00", source="paper")
    db.record_trade("ETHUSDT", "SHORT", 0.1, 200, 210, pnl=-2.0,
                    closed_at="2026-06-09T13:00:00", source="paper")
    trades = trades_from_rows(db.trades())
    s = summary(trades)
    assert s["total_pnl"] == -1.0
    assert s["count"] == 2


def test_paper_klijent_biljezi_trade_na_zatvaranje():
    from weexbot.weex import OrderRequest, PaperWeexClient
    from weexbot.weex.client import ENTRY_LIMIT, TAKE_PROFIT
    db = Database(":memory:")
    c = PaperWeexClient(balance=100.0, db=db)
    c.place_order(OrderRequest("ETHUSDT", "BUY", ENTRY_LIMIT, 0.01, price=2700))
    c.feed_price("ETHUSDT", 2700)
    c.place_order(OrderRequest("ETHUSDT", "SELL", TAKE_PROFIT, 0.01, price=2800, reduce_only=True))
    c.feed_price("ETHUSDT", 2800)                            # TP -> zatvaranje
    rows = db.trades()
    assert len(rows) == 1
    assert round(rows[0]["pnl"], 4) == round(0.01 * (2800 - 2700), 4)
