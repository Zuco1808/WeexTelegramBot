# -*- coding: utf-8 -*-
"""Korpus od 50 stvarnih uzoraka iz Telegram izvoza + ocekivana klasifikacija.

Format: (id, raw_text, expected_kind_value)
expected_kind_value odgovara SignalKind.value ("A_jeffrey", "C_bot", ...).

Poruka 1 (legenda) je skracena na reprezentativni isjecak (>300 znakova s
kljucnim frazama) - cijela je predugacka, a za test INFO detekcije je dovoljno.
Poruke 2-50 su prenesene vjerno (ukljucujuci emoji i zalijepljena polja iz HTML
ekstrakcije) kako bi testovi pokrili realne ulaze.
"""

_LEGEND = (
    "How to use signals in the channel. Hi friends, welcome to our additional "
    "scalping and intraday channel from the Insiders team. Two analysts will be "
    "working here: Jeffrey and Brandon. Jeffrey mostly shares scalping signals "
    "with exact parameters, and Brandon shares intraday signals with position "
    "entry zones. First, let's go over the general rules. It's best to trade "
    "futures using isolated margin. Always set your stop right away. No stop "
    "means no trade. Example: $BTCUSDT long entry 78964.2 stop 77032.2 take "
    "80522.8 leverage x17. Trade on WEEX no KYC."
)

SAMPLES: list[tuple[int, str, str]] = [
    (1, _LEGEND, "INFO"),
    (2, "$ETHUSDTlongentry - 2739.56; stop - 2632.84take - 2825.47; leverage - x11", "A_jeffrey"),
    (3, "$ETHUSDTlongentry - 2427.09; stop - 2350.75take - 2488.51; leverage - x13", "A_jeffrey"),
    (4, "$BTCUSDTlongentry - 78964.2; stop - 77032.2take - 80522.8; leverage - x17", "A_jeffrey"),
    (5, "XAUT/SHORT 15-40Entry point: 4,750–4,850TP:4,600 / fix 75%move stop to breakeven4,450 / fix 25%SL = 4,880", "B_zone"),
    (6, "XAG/SHORT 7-13Entry point: 77-82TP:73 / fix 75%move stop to breakeven67 / fix 25%SL = 83", "B_zone"),
    (7, "XAUT/SHORT 15-40Entry point: 4,750-4,850TP:4,600 / fix 75%move stop to breakeven", "B_zone"),
    (8, "XAUT/LONG x9-20Entry point: 4,750–4,950TP:5,205 / fix 75%move stop to breakeven5,500 / fix 25%SL = 4,695", "B_zone"),
    (9, "HBAR/SHORT x11-16Entry point: 0.09100-0.09500TP:0.08750 / fix 75%move stop to breakeven0.08300 / fix 25%SL = 0.09650", "B_zone"),
    (10, "SL to breakeven if desired", "E_update"),
    (11, "HBAR/SHORT x11-16Entry point: 0.09100-0.09500TP:0.08750 / we fix 75%move the stop to breakeven", "B_zone"),
    (12, "$BTCUSDTlongentry - 74456.2; stop - 72889.1take - 75744.3; leverage - x19", "A_jeffrey"),
    (13, "$BNBUSDTlongentry - 750.7; stop - 736.1take - 762.4; leverage - x22", "A_jeffrey"),
    (14, "SL to breakeven if desired", "E_update"),
    (15, "BTC/LONG x4-10Entry point: 70,000–77,000TP:82,250 / move stop to breakeven88,000 / fix 50%93,000 / fix 25%move stop to 2nd TP97,950 / fix 25%SL = 69,000", "B_zone"),
    (16, "ATOM/SHORT x8.5-16.5Entry point: 2.03-2.13TP:1.92 / fix 75%move stop to breakeven1.80 / fix 25%SL = 2.15", "B_zone"),
    (17, "XAG/LONG x17-23Entry point: 85.90-87.00TP:89.00 / fix 75%move stop to breakeven92.25 / fix 25%SL = 83.50", "B_zone"),
    (18, "SL to breakeven if desired", "E_update"),
    (19, "XAG/LONG x17-23Entry point: 85.90-87.00TP:89.00 / fix 75%move the stop to breakeven", "B_zone"),
    (20, "ETHUSDT 15mShortPrice: 2060.5TP2: 1932.92SL: 2195.0", "C_bot"),
    (21, "BTCUSDT 5mShortPrice: 69075.8TP2: 66265.9SL: 71944.4", "C_bot"),
    (22, "\U0001F4C9 ATOM/SHORT x8.5-16.5\U0001F4B5 Entry point: 2.03-2.13\U0001F37E TP:1.92 / fix 75%move the stop to breakeven", "B_zone"),
    (23, "ATOM/SHORT x8.5-16.5Entry point: 2.03-2.13TP:1.80 / fix.", "B_zone"),
    (24, "LTC/SHORT 2.5-6.5Entry point: 77.00-85.00TP:48.60 / fixed.", "B_zone"),
    (25, "ASTERUSDT 5mShortPrice: 0.5442TP1: 0.5305SL: 0.5589", "C_bot"),
    (26, "BTCUSDT 5mLongPrice: 69432.1TP1: 69814.0SL: 68928.0", "C_bot"),
    (27, "Could've held it longer, if you're still in the trade - close 75%, move the stop to breakeven, and you can let the rest run toward higher targets70,80071,800", "E_update"),
    (28, "ETHUSDT 5mLongPrice: 2128.84TP1: 2173.97SL: 2067.16", "C_bot"),
    (29, "BTCUSDT 5mLongPrice: 70847.2TP1: 72646.3SL: 69055.0", "C_bot"),
    (30, "Had a nice pump in the moment, but we're waiting for take profit targets.", "UNKNOWN"),
    (31, "ASTERUSDT 3mShortPrice: 0.5934TP1: 0.5738SL: 0.6151", "C_bot"),
    (32, "SL", "E_update"),
    (33, "BTCUSDT 5mShortPrice: 69113.7TP2: 67711.3SL: 70499.9", "C_bot"),
    (34, "If you are holding short from the main channel - just keep it", "UNKNOWN"),
    (35, "ASTERUSDT 5mLongPrice: 0.633TP2: 0.6605SL: 0.598", "C_bot"),
    (36, "Short hit TP perfectly", "E_update"),
    (37, "BTC LongEntry: 67,000-66,000SL: 65,300", "D_manual"),
    (38, "TP:1. 679002. 691003. 70400", "E_update"),
    (39, "My current position. Average entry ~ 66,750", "UNKNOWN"),
    (40, "ETHUSDT 5mLongPrice: 1966.65TP2: 1999.92SL: 1930.39", "C_bot"),
    (41, "1TP✅Fix 30%", "E_update"),
    (42, "SL to breakeven", "E_update"),
    (43, "I'm trying a BTC short - very risky, so position size is smaller than usual.Entry levels:67,500-68,000Stop-loss: 68,300", "D_manual"),
    (44, "Position fully loaded. Slightly larger than planned, but the stop is tight, so I'll take the shotHigh probability of a stop-out here - manage risk carefully", "UNKNOWN"),
    (45, "Move SL to 68500", "E_update"),
    (46, "If we hit the stop, we'll look for the next short around 70,400", "UNKNOWN"),
    (47, "BTCUSDT 3mShortPrice: 67690.6TP2: 67041.3SL: 68265.5", "C_bot"),
    (48, "Guys, moving SL one more time, now it will be at 69200I think we might get a spike up at the US open", "E_update"),
    (49, "So, we're currently sitting in the middle of the range and saw a strong bounce. We managed to fix part of positions in time.", "UNKNOWN"),
    (50, "ZEC | LONGEntry: market / 226.44Target: 254.81Stoploss: 220.6Risk: 0,3% / 0.7%", "D_manual"),
]

# ID-evi koji se SMIJU (paper) tradeati u Fazi 1 (Format A + C, ne-metali).
TRADABLE_IDS = {2, 3, 4, 12, 13, 20, 21, 25, 26, 28, 29, 31, 33, 35, 40, 47}
