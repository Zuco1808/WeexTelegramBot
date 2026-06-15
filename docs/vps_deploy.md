# VPS deploy (24/7 live)

Cilj: pokrenuti bota non-stop na malom Linux VPS-u s **fiksnom javnom IP**
(whitelistaš je jednom na WEEX), neovisno o tvom računalu.

> Uvijek kreni **semi-auto** i sa **sićušnim iznosom**. Auto (`--auto`) tek kad
> stekneš povjerenje.

## 1) VPS i IP
- Uzmi mali VPS (Ubuntu 22.04+, 1 vCPU / 1 GB je dovoljno).
- Zapamti njegovu **statičnu javnu IP** i dodaj je u **WEEX → API Management → IP allowlist**.
- Provjeri da API ključ **nema** withdraw ovlasti (samo trade).

## 2) Instalacija
```bash
sudo apt update && sudo apt install -y python3-venv git
sudo adduser --disabled-password --gecos "" bot
sudo su - bot

# git preko SSH (preporuka za server) - dodaj deploy key na GitHub:
ssh-keygen -t ed25519 -C "vps-weexbot"        # pa kopiraj ~/.ssh/id_ed25519.pub na GitHub
git clone git@github.com:Zuco1808/WeexTelegramBot.git
cd WeexTelegramBot
python3 -m venv venv && . venv/bin/activate
pip install -r requirements.txt
```

## 3) .env na serveru (tajno)
```bash
cp .env.example .env && nano .env        # popuni WEEX + TELEGRAM kljuceve
chmod 600 .env                           # samo vlasnik cita
```
`.env` je u `.gitignore` — nikad se ne commita. Skripte ga same učitavaju.

## 4) Telethon prvi login (jednom, interaktivno)
Telethon prvi put traži broj + kod (kreira `data/tg_session`). Na serveru:
```bash
. venv/bin/activate
python run_telegram.py --backfill 5      # upiši broj i kod kad zatraži -> Ctrl+C
```
Nakon toga `data/tg_session` postoji i servis radi bez interakcije.

Provjeri vezu prije servisa:
```bash
python run_live_check.py                 # auth mora proci (IP whitelistana)
```

## 5) systemd servisi (auto-restart, boot)
`/etc/systemd/system/weexbot-telegram.service` (ingest, **semi-auto**):
```ini
[Unit]
Description=WeexTelegramBot ingest
After=network-online.target
Wants=network-online.target

[Service]
User=bot
WorkingDirectory=/home/bot/WeexTelegramBot
ExecStart=/home/bot/WeexTelegramBot/venv/bin/python run_telegram.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/weexbot-reconcile.service` (PnL ledger svjež):
```ini
[Unit]
Description=WeexTelegramBot reconcile loop
After=network-online.target

[Service]
User=bot
WorkingDirectory=/home/bot/WeexTelegramBot
ExecStart=/home/bot/WeexTelegramBot/venv/bin/python run_reconcile.py --loop --interval 300
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

Uključi:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now weexbot-telegram weexbot-reconcile
```

## 6) Nadzor i kočnice
```bash
journalctl -u weexbot-telegram -f          # uzivo log ingesta
journalctl -u weexbot-reconcile -f         # log reconcile petlje

# kill-switch (blokira slanje + otkazuje otvorene naloge):
cd /home/bot/WeexTelegramBot && . venv/bin/activate
python run_kill.py --on "panic" --cancel
python run_kill.py --off
```
Ako su Telegram alarmi konfigurirani (`TELEGRAM_BOT_TOKEN`/`TELEGRAM_ALERT_CHAT_ID`),
dobivaš poruke na signal / plasiran nalog / blokadu / kill.

## 7) Prelazak na auto (kad budeš sigurna)
```bash
sudo sed -i 's#run_telegram.py#run_telegram.py --auto#' /etc/systemd/system/weexbot-telegram.service
sudo systemctl daemon-reload && sudo systemctl restart weexbot-telegram
```

## 8) Update koda
```bash
cd /home/bot/WeexTelegramBot && git pull
sudo systemctl restart weexbot-telegram weexbot-reconcile
```

## Sigurnosne napomene
- API ključ: samo **trade** + **IP allowlist** (VPS IP), bez withdraw.
- Firewall: dopusti samo SSH (ufw). Bot ne treba otvorene portove.
- Dnevni stop (`DAILY_LOSS_LIMIT_USDT`) i limit pozicija (`MAX_CONCURRENT_POSITIONS`)
  rade automatski; `data/KILL` ima prednost nad svime.
- Vrijeme: kod koristi UTC; VPS neka bude na UTC (`timedatectl set-timezone UTC`).
