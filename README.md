# WEEX Telegram Bot — Faza 0 + 1

Parser trading signala iz Telegram izvoza, kao temelj za kasniji **WEEX paper-trading bot**.

> **Status:** Faza 0 (ekstrakcija) + Faza 1 (parser + testovi). Još **nema** trgovanja
> ni WEEX API-ja. Sve je lokalno i sigurno.

## Dogovorene postavke (Faza 1)

| Postavka | Vrijednost |
|---|---|
| Auto-trade formati | **Samo Jeffrey scalp (A) + bot (C)** |
| Brandon zone (B) | Parsiraju se, ali se **ne trguju** (Faza 2) |
| Leverage | Najniža iz raspona, **cap x10** (`LEVERAGE_CAP`) |
| Metali / nafta / dionice (XAUT, OIL, AAPL...) | **Podržano** na WEEX (USDT perpetual) — mapirano u `instruments.py` (GOLD→XAUTUSDT, OIL→XTIUSDT, ON→USDT) |
| Nepodržane dionice (PLTR, NVDA, TSLA, AMZN, META) | `SKIPPED_NOT_LISTED` (nije u WEEX listi) |
| Kapital (simulacija) | **100 USDT**, rizik **1%** po scalpu |
| Način rada | Paper / lokalno (nema API ključeva) |

## Struktura

```
WeexTelegramBot/
├── extract_messages.py     # FAZA 0: messages.html -> data/*.jsonl (čuva strukturu)
├── analyze.py              # pokreće parser + position sizing, ispis + data/parsed.jsonl
├── requirements.txt
├── pyproject.toml          # pytest pythonpath = src
├── src/weexbot/
│   ├── config.py           # sve konstante (cap, rizik, skip-simboli)
│   ├── models.py           # Signal, TakeProfit, Side, SignalKind, TradeStatus
│   ├── normalize.py        # Sloj 1: čišćenje teksta
│   ├── classify.py         # Sloj 2: koji je format poruke
│   ├── parser.py           # Sloj 3: ekstraktori po formatu + validacije
│   └── risk.py             # position sizing (rizik / |entry-stop|)
└── tests/
    ├── samples.py          # 50 stvarnih uzoraka + očekivana klasifikacija
    ├── test_normalize.py
    ├── test_classify.py    # klasifikacija nad svih 50
    └── test_parser.py      # ekstrakcija + SIGURNOSNI test (ništa chatter ≠ TRADABLE)
```

## Pokretanje

Sve ovisnosti (`beautifulsoup4`, `pytest`) već su prisutne, pa možeš odmah pokrenuti.
Ako želiš čisto okruženje:

```powershell
cd C:\PROJECT\WeexTelegramBot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 1) Testovi (rade bez HTML-a — koriste ugrađeni uzorak)
```powershell
python -m pytest -q
```
Očekivano: **116 passed**.

### 2) Analiza na ugrađenom uzorku (bez HTML-a)
```powershell
python analyze.py
```
Ispisuje sažetak po formatu, TRADABLE signale s position sizingom za 100 USDT,
i sprema `data/parsed.jsonl`.

### 3) Ekstrakcija iz tvog stvarnog izvoza (Faza 0)
```powershell
python extract_messages.py
# ili druga putanja:
python extract_messages.py --html "C:\put\do\messages.html"
```
Stvara `data/messages_all.jsonl` (sve poruke) i `data/signals_sample.txt`.
Nakon toga `python analyze.py` automatski koristi taj veći skup.

## Analiza formata (sažetak)

| Format | Primjer | Faza 1 |
|---|---|---|
| **A** Jeffrey | `$ETHUSDTlongentry - 2739.56; stop - 2632.84take - 2825.47; leverage - x11` | ✅ TRADABLE |
| **C** bot | `ETHUSDT 15mShortPrice: 2060.5TP2: 1932.92SL: 2195.0` | ✅ TRADABLE |
| **B** zona | `XAUT/SHORT 15-40Entry point: 4,750–4,850TP:4,600 / fix 75%…SL = 4,880` | ⏸ parsira se, ne trguje |
| **D** manual | `ZEC \| LONGEntry: market / 226.44Target: 254.81Stoploss: 220.6` | ⏸ ručni pregled |
| **E** update | `Move SL to 68500`, `1TP✅Fix 30%`, `SL to breakeven` | ⏸ Trade Manager (Faza 6) |
| INFO / chatter | legenda, komentari | ignorira se |

## Najvažniji test (sigurnost)

`test_parser.py::test_samo_dozvoljeni_idevi_su_tradable` provjerava da **nijedna**
update/komentar/legenda poruka nikada ne dobije status `TRADABLE`. To je mreža
koja sprječava da chatter završi kao živi nalog.

## Faza 2 — Persistencija + Paper broker (gotovo)

Novi moduli: `db.py` (SQLite), `symbols.py` (validacija/mapiranje), `paper_broker.py`
(gradi naloge bez API-ja), `pipeline.py` (poruka → parse → persist → paper nalozi).

```powershell
python run_paper.py        # napuni data/weex_paper.db i ispiše izvještaj
python run_paper.py --keep # zadrži postojeću bazu (test perzistencije)
```

Tablice: `signals`, `positions`, `orders`, `audit_log`, `account`.

- **Idempotentnost** (`message_id` UNIQUE): drugi prolaz ne stvara nijednu novu
  poziciju (sve `SKIPPED_DUPLICATE`). Provjereno na 882 poruke.
- Za svaki TRADABLE signal: 1 pozicija (`PLANNED`) + 3 naloga
  (`ENTRY_LIMIT` / `STOP_LOSS` reduce-only / `TAKE_PROFIT` reduce-only).
- Ne-tradable signali (B/D/E/INFO) se spremaju radi Trade Managera; chatter (UNKNOWN) se ignorira.
- **Limit istovremene izloženosti** (`config.MAX_OPEN_POSITIONS`, `MAX_PORTFOLIO_MARGIN_PCT`):
  novi signal koji bi prešao limit dobiva status `SKIPPED_EXPOSURE` (bez pozicije/naloga).
  Konzervativno: paper još ne simulira *zatvaranje*, pa sve `PLANNED` broji kao istovremeno
  (zato u mjesečnom replayu s defaultom 5 prolazi 5, a 16 ide u `SKIPPED_EXPOSURE`).

> Stvarni WEEX REST/WS adapter i točan format simbola dolaze u **Fazi 3** (treba API ključeve).

## Trade Manager (korelacija Brandon multi-message + update poruka)

Moduli: `manual_parser.py` (vadi činjenice iz pojedine poruke — par/smjer/ulaz/stop/
mete/namjere) i `trade_manager.py` (stateful sklapanje signala kroz više poruka +
usmjeravanje izmjena na ispravnu poziciju).

```powershell
python run_trade_manager.py            # sažetak + zadnjih 25 akcija
python run_trade_manager.py --all      # cijela vremenska linija
python run_trade_manager.py --review   # samo NEEDS_REVIEW
```

Akcije: `OPEN` (kad je nacrt potpun: smjer + ulaz + stop), `MOVE_SL`, `BREAKEVEN`,
`PARTIAL_CLOSE`, `CLOSE`, `EXPIRE`, `NEEDS_REVIEW`.

**Lifecycle pozicija** (smanjuje gomilanje „otvorenih" → manje lažne dvosmislenosti):
- eksplicitni `CLOSE` (stopped out / closed / fully close),
- **re-open zamjena**: novi `OPEN` istog para zatvara prethodnu poziciju,
- **stale expiry**: pozicija neaktivna > `config.TM_STALE_TICKS` (40) poruka → `EXPIRE`.

- **Multi-message**: par u jednoj poruci, entry/stop u sljedećoj → OPEN tek kad je potpun.
- **Korelacija izmjena**: eksplicitan par → ta pozicija; bez para i točno jedna
  otvorena → ta; **više otvorenih bez para → `NEEDS_REVIEW`** (pravilo „u nedoumici pitaj").
- Jeffrey/bot/legenda se preskaču (obrađuje ih pipeline) da ne kontaminiraju stanje.
- Sanity guardovi: zona s omjerom >10× se kolabira; OPEN s entry/stop koji se
  razlikuju >10× → `NEEDS_REVIEW` (filtrira šum iz ekstrakcije).

**Perzistencija:** `TradeManager(db=Database(...))` zapisuje sve akcije u `tm_actions`
i stanje pozicija u `tm_positions` (upsert po paru). `run_trade_manager.py` puni
`data/weex_paper.db`.

**Re-entry poruke:** miješan tekst koji zatvara prethodnu poziciju i opisuje novi
setup („Stopped out. Re-entry now OIL. Entry… TP… SL…") → zatvori prethodnu
(stopped out) + novi setup u `NEEDS_REVIEW` (management plana se NE primjenjuje na
staru poziciju).

**Više pozicija po paru (CORE/SCALP):** Brandon zna držati „long-term core" short
+ „scalp/added" poziciju na istom paru. TM ih drži odvojeno (tag `CORE`/`SCALP`) i
usmjerava izmjene po naznaci u tekstu („long-term" → CORE, „added/portion" → SCALP).
Kad par ima dvije pozicije, a izmjena nema naznaku → `NEEDS_REVIEW`.

**Ograničenja (za iduću iteraciju):** ekstrakcija na vrlo kratkim/malformiranim
fragmentima nije savršena, ali dvosmislenost uvijek završi kao `NEEDS_REVIEW`, ne kao
pogrešna akcija. Brandon (D) se i dalje **ne auto-trguje** — TM je za sada
korelacijski/analitički sloj.

**Učinak lifecycle-a na 882 poruke:** otvorenih na kraju **2** (prije 11),
`NEEDS_REVIEW` **118** (prije 133), od čega dvosmislenost zbog para palo s 118 na **85**.
Preostali review-i: 85 dvosmislenih (par nije naveden uz više otvorenih), 9 šum
ekstrakcije, 5 update bez otvorene pozicije, 2 close uz više parova — svi sigurno
označeni, nijedan kao pogrešna akcija. Točna simulacija zatvaranja na TP/SL traži
povijesne cijene (Faza 3).

## Izvještaji / dashboard

`reports.py` + `run_reports.py` — dnevni/sedmični/mjesečni pregled nad `trades`
ledgerom: **zeleno** dani u plusu (PnL + broj trejdova), **crveno** dani u minusu.

```powershell
python run_reports.py --seed-demo          # DEMO podaci -> vidiš format
python run_reports.py --html               # izvezi data/report.html
```

Sadrži: ukupni PnL/win rate/prosjek po trejdu, najbolji/najgori dan, equity
sparkline, te pregled **po simbolu**. `PaperWeexClient(db=...)` automatski upisuje
zatvorene trejdove u ledger.

> Pravi PnL po danima dolazi tek s cijenama u Fazi 3 (live/price feed). Do tada
> `--seed-demo` služi za prikaz formata.

## Go-live Quickstart

> Stvarni novac. Kreni **semi-auto** i sa **sićušnim iznosom**. Idealno na **VPS-u s
> fiksnom IP** (whitelistaj je jednom na WEEX) za rad 24/7.

```powershell
# 1) Okruženje
python -m venv venv; .\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2) .env (kopiraj .env.example) — popuni:
#    WEEX_API_KEY / WEEX_API_SECRET / WEEX_API_PASSPHRASE   (+ whitelistaj javnu IP)
#    TELEGRAM_API_ID / TELEGRAM_API_HASH / TELEGRAM_CHANNEL  (my.telegram.org)
#    (opc.) TELEGRAM_BOT_TOKEN / TELEGRAM_ALERT_CHAT_ID      (alarmi)

# 3) Provjera veze (ne šalje ništa)
python run_live_check.py

# 4) Praćenje kanala — SEMI-AUTO (javlja plan, ne trguje)
python run_telegram.py --backfill 20

# 5) Prvi pravi (sićušan) trade, ručno
python run_live_trade.py --text "...signal..." --yes --wait

# 6) Nakon zatvaranja: zabilježi PnL + dashboard
python run_reconcile.py
python run_reports.py --db weex_live.db --html

# 7) Tek kad stekneš povjerenje: auto slanje (u ±1% bandu)
python run_telegram.py --auto
```

**Kočnice (uvijek pri ruci):**
```powershell
python run_kill.py --on "panic" --cancel     # blokiraj sve + otkaži otvorene naloge
python run_kill.py --off                      # odmrzni
```
Sigurnosni gate (kill-switch, dnevni stop `DAILY_LOSS_LIMIT_USDT`, limit pozicija
`MAX_CONCURRENT_POSITIONS`) blokira slanje automatski. Alarmi (ako su konfigurirani)
javljaju na Telegram: signal / plasiran nalog / blokada / kill.

## Faza 3 — WEEX klijent (skeleton)

Paket `weex/`: jedinstveno sučelje `WeexClient`, paper implementacija s fill-ovima
na temelju cijene, i skeleton stvarnog REST klijenta.

```powershell
python run_weex_demo.py     # signal -> orders -> izvršenje na PaperWeexClient + PnL
```

- `WeexClient` (ABC): `set_leverage`, `place_order`, `cancel_order`, `open_orders`,
  `positions`, `mark_price` — isti potpis za paper i live (izvršni sloj se ne mijenja).
- `PaperWeexClient`: `feed_price(symbol, price)` izvršava naloge — ENTRY/ TP/ SL,
  reduce-only, **OCO** (kad pozicija padne na 0, par SL/TP se otkazuje). Vodi PnL i stanje.
  Ovo je ujedno simulacija TP/SL fill-ova koju lifecycle treba za točno zatvaranje.
- `RestWeexClient`: skeleton — `from_env()` čita `WEEX_API_KEY`/`WEEX_API_SECRET`
  (nikad u kodu; `.env.example` → `.env`), HMAC `_sign()` placeholder; sve metode bacaju
  `NotImplementedError` s jasnim TODO dok ne dobijemo ključeve i potvrdu endpointa/simbola.

**Što treba za live (Faza 3 dovršetak):** WEEX API ključevi, potvrda base URL-a,
formata potpisa i točnog simbol stringa iz WEEX dokumentacije, te WS/REST price feed
(da `feed_price` puni stvarne cijene umjesto demo vrijednosti).

### WEEX API ključevi

Ključevi se **nikad ne stavljaju u kod** — čitaju se iz okruženja preko
`config.weex_credentials()` / `RestWeexClient.from_env()`.

1. Na WEEX-u: **API Management → Create API** (Trade ovlasti za futures; preporuka:
   ograniči na IP allowlist, bez withdraw ovlasti).
2. Kopiraj `.env.example` u `.env` i popuni:

   ```dotenv
   WEEX_API_KEY=tvoj_api_key
   WEEX_API_SECRET=tvoj_api_secret
   WEEX_API_PASSPHRASE=tvoj_passphrase
   WEEX_BASE_URL=https://api-contract.weex.com
   ```

3. `.env` je u `.gitignore` — ne commitati ga. `run_live_check.py` ga učitava sam.

```powershell
python run_live_check.py            # READ-ONLY provjera veze (ne šalje naloge)
```

> Bez ključeva sve radi u paper modu (`PaperWeexClient`). `RestWeexClient` ima
> implementirano **čitanje** (server time, ticker/mark price, assets, positions);
> **pisanje** (place/cancel/leverage) dolazi u Fazi 3.2 nakon read-only validacije.

## Sljedeće

Live: popuniti `RestWeexClient` (REST + potpis) → price feed (WS) → spojiti TM/pipeline
na izvršni sloj → live Telegram ingestion (Telethon) → go-live s malim iznosom.
