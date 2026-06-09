"""RestWeexClient - SKELETON stvarnog WEEX REST klijenta (Faza 3).

Namjerno NE radi mrezne pozive: WEEX endpointi, format potpisa i tocan simbol
string potvrdjuju se uz sluzbenu WEEX API dokumentaciju i tek kad dobijemo
API kljuceve. Do tada svaka metoda baca NotImplementedError s jasnim TODO-om,
a `from_env()` validira da su kljucevi postavljeni (iz okruzenja, nikad u kodu).

Struktura (HMAC potpis, timestamp, _request) je tipicna za burze i sluzi kao
mjesto za popunjavanje kad krenemo na live.
"""
from __future__ import annotations

import hashlib
import hmac
import time

from ..config import WEEX_BASE_URL, weex_credentials
from .client import OrderRequest, OrderResult, PaperPosition, WeexClient

_TODO = ("Faza 3: spojiti na WEEX REST API. Potrebno: (1) WEEX API kljucevi u "
         "env-u (WEEX_API_KEY/WEEX_API_SECRET), (2) potvrda base URL-a i endpointa, "
         "(3) tocan format potpisa i simbola iz WEEX dokumentacije.")


class RestWeexClient(WeexClient):
    def __init__(self, api_key: str, api_secret: str, base_url: str = WEEX_BASE_URL):
        if not api_key or not api_secret:
            raise ValueError("Nedostaju WEEX API kljucevi (postavi u okruzenje).")
        if not base_url:
            raise ValueError("Nedostaje WEEX_BASE_URL (potvrditi iz WEEX dokumentacije).")
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")

    @classmethod
    def from_env(cls) -> "RestWeexClient":
        key, secret = weex_credentials()
        return cls(key or "", secret or "")

    # --- potpis (placeholder; tocan recept iz WEEX docs) ------------------ #
    def _sign(self, payload: str, timestamp: str) -> str:
        msg = f"{timestamp}{payload}".encode()
        return hmac.new(self.api_secret.encode(), msg, hashlib.sha256).hexdigest()

    def _request(self, method: str, path: str, params: dict | None = None) -> dict:
        # _ts za buduci potpis; mrezni poziv se dodaje u Fazi 3
        _ts = str(int(time.time() * 1000))
        raise NotImplementedError(_TODO)

    # --- WeexClient API (svi stubovi) ------------------------------------- #
    def set_leverage(self, symbol: str, leverage: float,
                     margin_mode: str = "isolated") -> None:
        raise NotImplementedError(_TODO)

    def place_order(self, req: OrderRequest) -> OrderResult:
        raise NotImplementedError(_TODO)

    def cancel_order(self, client_order_id: str) -> OrderResult:
        raise NotImplementedError(_TODO)

    def open_orders(self, symbol: str | None = None) -> list[OrderResult]:
        raise NotImplementedError(_TODO)

    def positions(self) -> list[PaperPosition]:
        raise NotImplementedError(_TODO)

    def mark_price(self, symbol: str) -> float | None:
        raise NotImplementedError(_TODO)
