# Faza 3 — Live na WEEX (plan korak po korak)

Cilj: od paper-only stoga doći do kontroliranog live trgovanja malim iznosom.
Zadržavamo dogovor: **semi-auto na početku** (čovjek potvrđuje svaki nalog) i
**Faza 1 opseg** (auto samo Jeffrey A + bot C; Brandon D ostaje ručni/semi-auto).

Sve niže gradi na postojećem: `weex/WeexClient` (ABC, isti potpis za paper i live),
`RestWeexClient` (skeleton), `PaperWeexClient`, `pipeline.py`, `trade_manager.py`,
`instruments.py` (mapiranje simbola).

---

## 3.0 — Preduvjeti (blokira sve ostalo)
- [ ] WEEX API ključevi (Trade ovlasti za futures, IP allowlist, **bez withdraw**) — vidi README.
- [ ] Službena WEEX API dokumentacija: base URL, format **HMAC potpisa**, headeri,
      točni endpointi, **točan simbol string** (npr. `BTCUSDT` vs `cmt_btcusdt`).
- [ ] Demo/testnet okruženje ako postoji (inače: read-only + minimalni iznos na live).
- **Rezultat:** `.env` popunjen; `RestWeexClient.from_env()` ne baca `ValueError`.

## 3.1 — REST klijent: read-only prvo
- [ ] `_request()` u `RestWeexClient`: `httpx`, timestamp, `_sign()`, headeri, parsiranje.
- [ ] Implementiraj **samo čitanje**: `mark_price()`, `positions()`, `open_orders()`.
- [ ] Rukovanje greškama: rate-limit (429), retry s backoffom, jasne iznimke.
- **Acceptance:** dohvat cijene i (praznih) pozicija s live accounta; ništa se ne mijenja.
- **Test:** integracijski test iza `WEEX_LIVE_TESTS=1` flaga (ne u CI bez ključeva).

## 3.2 — REST klijent: pisanje (na demo / sićušan iznos)
- [ ] `set_leverage()` (+ isolated margin), `place_order()`, `cancel_order()`.
- [ ] Mapiranje simbola preko `instruments.resolve_symbol` (već postoji).
- [ ] Idempotentnost: `client_order_id` iz `paper_broker.build_orders` (već postoji).
- **Acceptance:** postavi → provjeri → otkaži limit nalog daleko od cijene; 0 zaostalih naloga.
- **Sigurnost:** tvrdi limiti (min notional, max leverage `LEVERAGE_CAP`).

## 3.3 — Reconciliation & lifecycle s burze
- [ ] Na live-u SL/TP su **pravi reduce-only nalozi** na burzi; ne simuliramo `feed_price`.
- [ ] User-data stream (WS) ili polling: pratiti fill-ove, zatvaranja, partial fill.
- [ ] Sinkronizacija stanja na startu (pozicije/nalozi iz burze → naša baza).
- **Acceptance:** kad SL/TP odradi na burzi, naša pozicija ide u `CLOSED` (bez stale-expiry heuristike).

## 3.4 — Price feed (WS)
- [ ] WS ticker/mark-price → cache; koristi za monitoring, alarme i (opcionalno) backtest.
- [ ] Reconnect/heartbeat, throttling.
- **Acceptance:** stabilan stream cijena za aktivne simbole.

## 3.5 — Spoj pipeline → izvršenje (semi-auto)
- [ ] `MODE` env: `paper` (default) | `live`. `paper` → `PaperWeexClient`, `live` → `RestWeexClient`.
- [ ] Za svaki TRADABLE A/C signal: generiraj nalog → **traži potvrdu** (CLI/Telegram/dashboard) → pošalji.
- [ ] Provjera pravila iz Poruke 1: likvidacija ne smije biti bliža od SL-a.
- **Acceptance:** end-to-end jedan realni mali trade uz ručnu potvrdu; zapis u `audit_log`.

## 3.6 — Live Telegram ingestion (Telethon)
- [ ] Telethon klijent sluša kanal → `pipeline.process` (A/C) i `TradeManager.process` (D/E).
- [ ] Dedup po `message_id`, reconnect, rate-limit.
- [ ] **Napomena:** Telethon koristi osobni account — potvrditi je li OK ili Bot API.
- **Acceptance:** poruke stižu u realnom vremenu i ispravno se rutiraju.

## 3.7 — Ops & go-live
- [ ] **Kill-switch** (zaustavi sve, otkaži otvorene naloge).
- [ ] Limit istovremene izloženosti (već u pipeline-u) + dnevni gubitak stop.
- [ ] Strukturirano logiranje + alarmi (Telegram/email) na greške i fill-ove.
- [ ] Go-live: read-only → demo → **sićušan realni iznos** → postupno skaliranje.
- [ ] Prijelaz semi-auto → auto tek nakon 2–4 tjedna stabilnog rada.

---

## Redoslijed (ovisnosti)
```
3.0 → 3.1 → 3.2 → 3.3 ─┐
                3.4 ────┼→ 3.5 → 3.6 → 3.7
```

## Što NE mijenjamo
- Parser/Trade Manager logika (gotova, 187 testova) — Faza 3 samo dodaje izvršni sloj.
- `WeexClient` sučelje — `RestWeexClient` se popunjava bez diranja pozivatelja.

## Otvorena pitanja za korisnika (prije 3.5/3.6)
1. Potvrda iznosa i `LEVERAGE_CAP` za live (trenutno simulacija 100 USDT / cap x10).
2. Semi-auto potvrda: CLI, Telegram poruka ili mali web dashboard?
3. Telethon (osobni account) vs Bot API za ingestion?
4. Auto-trade samo A/C, ili i podržani TradFi (XAUT/OIL…) iz Brandona kad bude spreman?
