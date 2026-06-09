# Nalazi iz punog izvoza (882 poruke) — ulaz za Fazu 2

> Faza 1 parser (Jeffrey A + bot C) je validiran na cijelom skupu: 21 TRADABLE
> (5 A + 16 C), 0 propustenih, 0 laznih. Ovaj dokument hvata sto je VECI skup
> otkrio, a sto Faza 1 namjerno NE rjesava.

## Raspodjela na 882 poruke

| Format | Broj | Faza 1 |
|---|---|---|
| A_jeffrey | 5 | TRADABLE |
| C_bot | 16 | TRADABLE |
| B_zone | 13 | parsira se, ne trguje |
| D_manual | 39 | samo klasifikacija |
| E_update | 147 | samo klasifikacija |
| UNKNOWN | 661 | chatter / analiza |
| INFO | 1 | legenda |

Stvarni kanal je **dominantno Brandonov rucni intraday + upravljanje pozicijom**,
a ne cisti scalp. Cisti A/C signali (oni koje trgujemo) su manjina, ali su 100%
strukturirani i pouzdano se parsiraju.

## NAJVAZNIJI nalaz: Brandon je cesto MULTI-MESSAGE

Jedan logicki signal se rasporedi kroz vise poruka. Primjeri (po ID-u u izvozu):

- msg148 „Trying another short on BTC… Stop at 70,700." → msg150 „Entry: 69,500-70,200"
- msg301 „BTC Short / Small size" → msg303 „BTC / Entry 68,100-68,300 / SL 68,950"
- msg352 „BTC Short here" → msg354 „BTC / Entry 64400-65000 / Stop 65600 / Target 62000"
- msg365/366 „BTC/ETH Short now" → msg368/369 (entry zone/stop/target) → msg372 „managing…"

Posljedica za arhitekturu: **Trade Manager (Faza 6) mora drzati „otvoreni nacrt
signala" po paru i nadopunjavati ga sljedecim porukama** (pair → entry → stop →
target → update…), a ne tretirati svaku poruku izolirano.

## Brandon manual (D) — stvarne varijacije koje treba pokriti u Fazi 2

Par/smjer:
- `ASTER | LONG`, `XAUT / LONG`, `EGLDUSDT | LONG`, `PUMPUSDT LONG`
- `BTC Long`, `ETH Short`, samo `BTC` / `ETH` (par u prethodnoj poruci)

Ulaz (sve ove varijante postoje):
- `Entry:` · `Entries:` · `Entry zone:` · `Entry range:` · `Entry` (bez dvotocke)
- jedan limit `market / 226.44`; dvije cijene `4.295 / 4.065`; raspon `66,800 – 64,800`

Stop:
- `Stop:` · `Stop` · `SL:` · `SL` · `Stop Loss` · `Stop-loss:` · `SL for now:`

Target:
- `Target:` · `Targets: 0.73 / 0.743 / 0.753$` · `TP:` · `First target 1940`
- `1 Target - 0.021` · `Final take-profit: 65,450`

Primjeri cistih, parsabilnih D signala (kandidati za trade u Fazi 2/3):
```
ASTER | LONG
Entry: 0,7112 / 0,7043$
Targets: 0.73 / 0.743 / 0.753$
SL: 0.6951$
```
```
EGLDUSDT | LONG  (Limit order!)
Entry: 4.295 / 4.065
Targets: 4.745 / 4.93 / 5.087
Stop: 3.654
```

## Update poruke (E) cesto NOSE par — dobra vijest za korelaciju (Q6)

- msg215 `ETH / SL to breakeven`
- msg216 `BTC / Moving SL to 64,700`
- msg356 `BTC Stop to 66100` · msg357 `ETH stop to 1955`
- msg266 `FFUSDT / 50% take here` · msg269 `PUMPUSDT / 50% close / SL to breakeven`
- msg307 `BTC ETH / Close 30% of both positions and SL to breakeven` (DVA para!)

Zakljucak: korelacija po paru je izvediva u vecini slucajeva; „u nedoumici pitaj"
ostaje fallback samo kad par nije naveden ili je dvosmislen.

## Zamke za normalizaciju/ekstrakciju (Faza 2)

1. **Decimalni zarez u stvarnim signalima:** `SL - 1,4972` (XRP), `0,7112`, `Risk: 0,3%`.
   Trenutni `normalize` ispravno CUVA decimalni zarez (ne brise ga kao tisucicu),
   ali ekstraktor D mora `,`→`.` pretvoriti po polju prije `float()`.
2. **`$` sufiks na cijeni:** `0.753$`, `0.6951$` — strip prije parse.
3. **Stats poruke** (`SCALPING TRADING STATS`, `BTC LONG +$1182 / 49%`) sadrze
   par+smjer+brojeve i mogu lazno izgledati kao signal. Trenutno → UNKNOWN (sigurno),
   ali u Fazi 2 dodati eksplicitan STATS detektor radi ciste statistike.
4. **`Entry zone:` kod metala** (msg385 `XAUT / LONG … Entry zone … close 75% … SL:`)
   trenutno padne u E_update. Bezopasno (metal se ionako preskace), ali B/ D parser
   u Fazi 2 treba prihvatiti i „Entry zone/range" i „close NN%" (uz „fix NN%").

## Sto NE mijenjati sad

Faza 1 opseg (trade samo A+C) je ispunjen i siguran. Gore navedeno je posao za
Fazu 2 (persistencija + WEEX paper) i Fazu 6 (Trade Manager / multi-message).
