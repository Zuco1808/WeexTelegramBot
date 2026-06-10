# -*- coding: utf-8 -*-
"""Testovi Trade Managera: multi-message sklapanje + korelacija update poruka."""
from weexbot.trade_manager import TradeManager


def _kinds(actions):
    return [a.kind for a in actions]


def test_multi_message_open():
    """Par+stop u jednoj poruci, entry u sljedecoj -> OPEN tek kad je potpun."""
    tm = TradeManager()
    a1 = tm.process("m148", "Trying another short on BTC from current levels. Stop at 70,700.")
    assert a1 == []                              # jos nema entry
    a2 = tm.process("m150", "Entry: 69,500-70,200")
    assert _kinds(a2) == ["OPEN"]
    pos = tm.open_positions()["BTC"]
    assert pos.side == "SHORT"
    assert pos.entry_zone == (69500.0, 70200.0)
    assert pos.stop == 70700.0


def test_dvije_pozicije_i_routing_move_sl():
    tm = TradeManager()
    tm.process("m352", "BTC Short here")
    tm.process("m353", "ETH Short here")
    tm.process("m354", "BTC / Entry 64400-65000 / Stop 65600 / Target 62000")
    tm.process("m355", "ETH / Entry 1890-1910 / Stop Loss 1937 / Target 1700")
    assert set(tm.open_positions()) == {"BTC", "ETH"}

    a_btc = tm.process("m356", "BTC Stop to 66100")
    assert _kinds(a_btc) == ["MOVE_SL"]
    assert a_btc[0].pair == "BTC"
    assert tm.position("BTC").stop == 66100.0

    a_eth = tm.process("m357", "ETH stop to 1955")
    assert a_eth[0].pair == "ETH"
    assert tm.position("ETH").stop == 1955.0
    # BTC ostao netaknut
    assert tm.position("BTC").stop == 66100.0


def test_breakeven_postavlja_stop_na_entry():
    tm = TradeManager()
    tm.process("m1", "ETH Long")
    tm.process("m2", "ETH / Entry 2000 / Stop 1950")
    assert tm.position("ETH").entry == 2000.0
    a = tm.process("m3", "ETH SL to breakeven")
    assert _kinds(a) == ["BREAKEVEN"]
    assert tm.position("ETH").stop == 2000.0


def test_update_bez_para_jedna_otvorena():
    tm = TradeManager()
    tm.process("m1", "BTC Long")
    tm.process("m2", "BTC / Entry 67000 / Stop 65000")
    a = tm.process("m3", "Move SL to 66000")        # nema para, ali samo 1 otvorena
    assert _kinds(a) == ["MOVE_SL"]
    assert tm.position("BTC").stop == 66000.0


def test_update_bez_para_vise_otvorenih_je_needs_review():
    tm = TradeManager()
    tm.process("m1", "BTC Long")
    tm.process("m2", "BTC / Entry 67000 / Stop 65000")
    tm.process("m3", "ETH Long")
    tm.process("m4", "ETH / Entry 2000 / Stop 1950")
    a = tm.process("m5", "SL to breakeven")          # dvosmisleno
    assert _kinds(a) == ["NEEDS_REVIEW"]
    # nista nije promijenjeno
    assert tm.position("BTC").stop == 65000.0
    assert tm.position("ETH").stop == 1950.0


def test_dva_para_u_jednoj_update_poruci():
    tm = TradeManager()
    tm.process("m1", "BTC Short here")
    tm.process("m2", "BTC / Entry 64400-65000 / Stop 65600")
    tm.process("m3", "ETH Short here")
    tm.process("m4", "ETH / Entry 1890-1910 / Stop 1937")
    a = tm.process("m5", "BTC ETH Close 30% of both positions and SL to breakeven")
    kinds = _kinds(a)
    assert kinds.count("BREAKEVEN") == 2
    assert kinds.count("PARTIAL_CLOSE") == 2
    assert tm.position("BTC").remaining_pct == 70
    assert tm.position("ETH").remaining_pct == 70


def test_core_i_scalp_na_istom_paru_routing_po_tagu():
    """Brandon: long-term core short + scalp short na istom BTC; izmjene po tagu."""
    tm = TradeManager()
    tm.process("s1", "BTC Short here\nEntry: 61400-62200\nSL: 63250")           # SCALP
    tm.process("c1", "BTC long-term short\nEntry: 70000-72000\nSL: 75000")      # CORE
    assert tm.position("BTC", "SCALP").stop == 63250.0
    assert tm.position("BTC", "CORE").stop == 75000.0
    assert len(tm.all_open()) == 2

    # izmjena koja spominje "long-term" -> ide na CORE, scalp netaknut
    a = tm.process("u1", "Move the long-term stop to 68300")
    assert _kinds(a) == ["MOVE_SL"]
    assert a[0].detail["tag"] == "CORE"
    assert tm.position("BTC", "CORE").stop == 68300.0
    assert tm.position("BTC", "SCALP").stop == 63250.0


def test_dvije_pozicije_isti_par_bez_taga_je_review():
    tm = TradeManager()
    tm.process("s1", "BTC Short here\nEntry: 61400-62200\nSL: 63250")
    tm.process("c1", "BTC long-term short\nEntry: 70000-72000\nSL: 75000")
    a = tm.process("u1", "Move stop to 64000")        # nema naznake core/scalp
    assert _kinds(a) == ["NEEDS_REVIEW"]
    assert "core/scalp" in a[0].detail["reason"]
    # nista nije promijenjeno
    assert tm.position("BTC", "SCALP").stop == 63250.0
    assert tm.position("BTC", "CORE").stop == 75000.0


def test_tiered_alokacija_se_cuva_na_poziciji():
    # PLTR nije podrzan -> umjesto njega koristimo podrzani par za tiered ulaz.
    tm = TradeManager()
    a = tm.process("m1", "ETH Long\nEntry:\n1. 1650 - 30%\n2. 1600 - 70%\nSL: 1550")
    assert _kinds(a) == ["OPEN"]
    assert a[0].detail["entry_tiers"] == [(1650.0, 30), (1600.0, 70)]
    assert tm.position("ETH").entry_tiers == [(1650.0, 30), (1600.0, 70)]


def test_reentry_zatvara_staru_i_flaga_novi_setup():
    # #5: "Stopped out. Re-entry now OIL. Entry... TP1... SL..."
    tm = TradeManager()
    tm.process("m1", "BTC Long")
    tm.process("m2", "BTC / Entry 67000 / Stop 65000")
    a = tm.process("m3", "Stopped out.\nRe-entry now OIL.\nEntry: 87\nSecond entry: 82\n"
                         "TP1: 96 - take 50%, move stop to breakeven\nSL: 78.8")
    kinds = _kinds(a)
    assert "CLOSE" in kinds              # stara BTC zatvorena (stopped out)
    assert "NEEDS_REVIEW" in kinds       # novi OIL setup -> rucni pregled
    assert "BTC" not in tm.open_positions()
    # management novog plana NIJE primijenjen kao izmjena na staru poziciju
    assert "PARTIAL_CLOSE" not in kinds
    assert "MOVE_SL" not in kinds


def test_building_bez_para_je_needs_review():
    tm = TradeManager()
    a = tm.process("m1", "Trying a small LONG here.")
    assert _kinds(a) == ["NEEDS_REVIEW"]


def test_xmr_se_prepoznaje_i_ne_otima_drugi_par():
    """Regresija: prije je XMR signal (nepoznat par) preuzimao current_pair."""
    tm = TradeManager()
    tm.process("p1", "PUMP Long")
    tm.process("p2", "PUMP / Entry 0.0014 / Stop 0.0012")
    a = tm.process("x1", "XMR Long\nEntry: 289-296\nSL: 283")
    assert _kinds(a) == ["OPEN"]
    assert a[0].pair == "XMR"                      # ne PUMP!
    assert tm.open_positions()["PUMP"].side == "LONG"   # PUMP netaknut


def test_nepoznat_ticker_ide_u_review_a_ne_otima():
    tm = TradeManager()
    tm.process("b1", "BTC Short here")
    tm.process("b2", "BTC / Entry 64000-65000 / Stop 66000")
    # vodeci STVARNO neprepoznat ticker (ZZZ) -> ne smije oteti BTC poziciju
    a = tm.process("o1", "ZZZ Long\nEntry: 87-90\nSL: 78")
    assert _kinds(a) == ["NEEDS_REVIEW"]
    assert tm.open_positions()["BTC"].stop == 66000.0   # BTC netaknut


def test_pairless_fragment_nastavlja_current_pair():
    # fragment bez tickera (samo entry/stop) nastavlja zadnji par
    tm = TradeManager()
    tm.process("b1", "BTC Short here")
    a = tm.process("b2", "Entry 64000-65000\nStop 66000")   # nema para -> BTC
    assert _kinds(a) == ["OPEN"]
    assert a[0].pair == "BTC"


def test_nepodrzana_dionica_se_skipa():
    # PLTR nije u WEEX listi -> SKIPPED_NOT_LISTED
    tm = TradeManager()
    a = tm.process("p1", "PLTR Long\nEntry: 136.5\nSL: 122\nTarget: 156")
    assert _kinds(a) == ["SKIPPED_NOT_LISTED"]
    assert a[0].pair == "PLTR"
    assert tm.open_positions() == {}


def test_podrzani_tradfi_se_otvara_kao_pozicija():
    # OIL je sada PODRZAN na WEEX-u -> otvara se normalno (ne skipa se)
    tm = TradeManager()
    a = tm.process("o1", "OIL Long\nEntry: 87-90\nSL: 78")
    assert _kinds(a) == ["OPEN"]
    assert a[0].pair == "OIL"
    assert tm.open_positions()["OIL"].side == "LONG"


def test_nepodrzana_dionica_ne_otima_kripto_poziciju():
    tm = TradeManager()
    tm.process("b1", "BTC Short here")
    tm.process("b2", "BTC / Entry 64000-65000 / Stop 66000")
    a = tm.process("o1", "PLTR Long\nEntry: 136.5\nSL: 122")
    assert _kinds(a) == ["SKIPPED_NOT_LISTED"]
    assert tm.open_positions()["BTC"].stop == 66000.0   # kripto pozicija netaknuta


def test_full_close_zatvara():
    tm = TradeManager()
    tm.process("m1", "PUMP Long")
    tm.process("m2", "PUMP / Entry 0.0014 / Stop 0.0012")
    a = tm.process("m3", "PUMP\nFull close")
    assert _kinds(a) == ["CLOSE"]
    assert "PUMP" not in tm.open_positions()


def test_close_zatvara_poziciju():
    tm = TradeManager()
    tm.process("m1", "BTC Long")
    tm.process("m2", "BTC / Entry 67000 / Stop 65000")
    a = tm.process("m3", "Stopped out")
    assert _kinds(a) == ["CLOSE"]
    assert "BTC" not in tm.open_positions()


def test_reopen_zamjenjuje_staru_poziciju():
    tm = TradeManager()
    tm.process("m1", "BTC Long")
    tm.process("m2", "BTC / Entry 67000 / Stop 65000")
    tm.process("m3", "BTC Short here")
    a4 = tm.process("m4", "BTC / Entry 70000 / Stop 71000")
    # m4 treba zatvoriti staru (CLOSE) pa otvoriti novu (OPEN)
    assert _kinds(a4) == ["CLOSE", "OPEN"]
    assert len(tm.open_positions()) == 1
    assert tm.open_positions()["BTC"].side == "SHORT"
    assert tm.open_positions()["BTC"].stop == 71000.0


def test_stale_expiry_zatvara_neaktivnu_poziciju():
    tm = TradeManager(stale_ticks=2)
    tm.process("m1", "BTC Long")                       # tick1
    tm.process("m2", "BTC / Entry 67000 / Stop 65000")  # tick2 -> OPEN, last_tick=2
    assert "BTC" in tm.open_positions()
    tm.process("c1", "some random commentary here")     # tick3 (3-2=1)
    tm.process("c2", "more random commentary here")     # tick4 (4-2=2)
    a = tm.process("c3", "even more commentary here")    # tick5 (5-2=3 > 2) -> EXPIRE
    assert "EXPIRE" in _kinds(a)
    assert "BTC" not in tm.open_positions()


def test_aktivnost_odgada_expiry():
    tm = TradeManager(stale_ticks=2)
    tm.process("m1", "BTC Long")
    tm.process("m2", "BTC / Entry 67000 / Stop 65000")  # tick2
    tm.process("c1", "random commentary one")            # tick3
    tm.process("m4", "BTC Stop to 66000")                # tick4 -> aktivnost, last_tick=4
    tm.process("c2", "random commentary two")            # tick5 (5-4=1)
    assert "BTC" in tm.open_positions()                  # jos zivo
