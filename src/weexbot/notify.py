"""Alarmi (Faza 3.7+) - Telegram Bot API obavijesti (place/kill/blok/stop).

Koristi obican HTTPS (stdlib urllib) - radi iz bilo koje skripte, ne treba telethon.
Postavi bota preko @BotFather, uzmi token i svoj chat_id (npr. preko @userinfobot).

env: TELEGRAM_BOT_TOKEN, TELEGRAM_ALERT_CHAT_ID. Ako nisu postavljeni -> NullNotifier.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from .config import telegram_alert_config


class Notifier:
    def send(self, text: str) -> bool:
        raise NotImplementedError


class NullNotifier(Notifier):
    """Bez konfiguracije - tiho ne radi nista (vraca False)."""
    def send(self, text: str) -> bool:
        return False


class TelegramNotifier(Notifier):
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id

    def send(self, text: str) -> bool:
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        data = json.dumps({"chat_id": self.chat_id, "text": text}).encode()
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10):
                return True
        except (urllib.error.URLError, OSError):
            return False


def notifier_from_env() -> Notifier:
    token, chat_id = telegram_alert_config()
    if token and chat_id:
        return TelegramNotifier(token, chat_id)
    return NullNotifier()
