# Changelog

Format prema [Keep a Changelog](https://keepachangelog.com/). Projekt je u
aktivnom razvoju (pre-1.0); verzije nisu još taggane.

## [Unreleased]

### Dodano
- **Ekstrakcija (Faza 0):** `extract_messages.py` — Telegram HTML → JSONL uz
  očuvanje strukture (`<br>` → novi red).
- **Parser (Faza 1):** slojeviti `normalize → classify → extract`; formati
  A (Jeffrey scalp), B (zona), C (bot), D (manual), E (update), INFO.
- **Persistencija (Faza 2):** SQLite (`signals/orders/positions/audit` + `tm_*`),
  idempotentnost preko `message_id`.
- **Risk + paper broker:** position sizing (1 % rizik); `ENTRY/STOP_LOSS/TAKE_PROFIT`
  nalozi; limit istovremene izloženosti (`SKIPPED_EXPOSURE`).
- **Trade Manager:** korelacija multi-message Brandon signala + update poruka
  (`OPEN/MOVE_SL/BREAKEVEN/PARTIAL_CLOSE/CLOSE/EXPIRE/NEEDS_REVIEW`).
  - Lifecycle pozicija: eksplicitni close, re-open zamjena, stale expiry.
  - **Više pozicija po paru** (tag `CORE`/`SCALP`) s usmjeravanjem izmjena po tagu.
  - **Re-entry** poruke (zatvori prethodnu + novi setup → ručni pregled).
  - Ekstrakcija numeriranih TP-ova, tiered ulaza i **tiered alokacije** (`entry_tiers`).
- **WEEX klijent (Faza 3 skeleton):** `WeexClient` (ABC), `PaperWeexClient`
  (fill-ovi na temelju cijene, OCO, PnL), `RestWeexClient` (skeleton; ključevi iz env-a).
- **Instrumenti:** registar podržanih WEEX simbola (kripto + TradFi/RWA) s mapiranjem
  na USDT perpetual (GOLD→XAUTUSDT, OIL→XTIUSDT, dionice→+USDT, `ON`→USDT).
- **Izvještaji / dashboard:** `reports.py` + `run_reports.py` — dnevni/sedmični/mjesečni
  PnL (zeleno plus / crveno minus, broj trejdova, win rate), po simbolu, najbolji/najgori
  dan, equity sparkline (terminal) i **SVG equity curve grafikon** u HTML izvozu;
  `trades` ledger u SQLite (puni ga `PaperWeexClient`).

### Promijenjeno
- TradFi (metali/nafta/dionice) **više se ne preskaču** — podržani su na WEEX-u uz
  USDT kolateral (po službenoj listi). Skipaju se samo nepodržane dionice
  (`SKIPPED_NOT_LISTED`: PLTR/NVDA/TSLA/AMZN/META).

### Popravljeno
- Detekcija para: regex je „pojeo" USDT sufiks (EGLD/FF/PUMP/ASTERUSDT nisu bili
  prepoznati i otimali su `current_pair`).
- Nepoznat ticker više ne preuzima tuđu poziciju (→ `NEEDS_REVIEW`).
- Bolja detekcija zatvaranja (`full close`, `closing…completely`).

### Faza 3 (live, u tijeku)
- **3.1 READ-ONLY (gotovo, uživo):** `RestWeexClient` (WEEX contract API, Bitget-stil
  potpis: `base64(HMAC_SHA256(secret, ts+METHOD+path+body))`, headeri ACCESS-KEY/SIGN/
  PASSPHRASE/TIMESTAMP). Dvije sheme simbola: v3 `BTCUSDT`, v2 `cmt_btcusdt`. Metode:
  server_time, ticker/mark_price, account_assets, raw_positions, exchange_info,
  raw_open_orders. `run_live_check.py` validacija.
- **3.2 WRITE (gotovo, uživo):** `set_leverage` (isolated), `place_order` (type 1/2/3/4,
  limit/market, marginMode isolated, preset SL/TP podržan), `cancel_order`, tipizirani
  `open_orders`/`positions`. Potvrđeno uživo malim limitom (place→cancel). **Jedinica
  `size` = bazni coin** (WEEX računa ugovore = size/contractVal). `run_live_order_test.py`.
- **3.5 EXECUTOR (semi-auto):** `LiveExecutor` — Signal→WEEX: stvarni balans za sizing
  (2% rizik), per-simbol zaokruživanje (`symbol_spec`), leverage cap isolated, entry
  limit + **preset SL/TP**; entry izvan ±1% banda → čeka da uđe (`--wait`).
  `run_live_trade.py` (semi-auto, `--yes`, safety `--max-notional`).
- **3.3 RECONCILIATION:** `Reconciler` čita `order_history`, bilježi realizirani PnL
  zatvorenih (`close_long`/`close_short`, `totalProfits`) u `trades` ledger (dedup po
  `order_id`/`ext_id`) → **dashboard prikazuje stvarni PnL**. `run_reconcile.py`
  (→ `data/weex_live.db`), `run_reports.py --db weex_live.db`.
- **3.6 TELEGRAM INGEST:** `SignalRouter` (čista logika: dedup, parse, ruta A/C→izvršitelj
  semi-auto / D/E→Trade Manager / chatter→ignore). `run_telegram.py` (Telethon transport,
  lazy import) — default **semi-auto** (javi plan), `--auto` šalje u bandu, `--backfill N`.

### Opseg
- Auto-trade u Fazi 1: **samo** Jeffrey (A) + bot (C), sve kripto-USDT.
- Live: semi-auto + sićušan iznos; cap x10, rizik 2%, isolated. 201 test.
