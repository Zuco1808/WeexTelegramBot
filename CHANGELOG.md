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
  dan, equity sparkline, HTML izvoz; `trades` ledger u SQLite (puni ga `PaperWeexClient`).

### Promijenjeno
- TradFi (metali/nafta/dionice) **više se ne preskaču** — podržani su na WEEX-u uz
  USDT kolateral (po službenoj listi). Skipaju se samo nepodržane dionice
  (`SKIPPED_NOT_LISTED`: PLTR/NVDA/TSLA/AMZN/META).

### Popravljeno
- Detekcija para: regex je „pojeo" USDT sufiks (EGLD/FF/PUMP/ASTERUSDT nisu bili
  prepoznati i otimali su `current_pair`).
- Nepoznat ticker više ne preuzima tuđu poziciju (→ `NEEDS_REVIEW`).
- Bolja detekcija zatvaranja (`full close`, `closing…completely`).

### Opseg
- Auto-trade u Fazi 1: **samo** Jeffrey (A) + bot (C), sve kripto-USDT.
- Sve paper/lokalno (bez WEEX API ključeva). 187 testova.
