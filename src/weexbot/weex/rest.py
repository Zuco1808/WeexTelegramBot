"""RestWeexClient - WEEX contract (futures) REST klijent.

Faza 3.1: implementirano SAMO ČITANJE (server time, ticker/mark price, assets,
positions). Pisanje (place_order/cancel/set_leverage) je Faza 3.2 - tek nakon
validacije read-only i potvrde tocnih parametara naloga iz dokumentacije.

Auth (WEEX/Bitget-stil):
  message = timestamp + METHOD + requestPath(+"?"+query) + body
  sign    = base64(HMAC_SHA256(secretKey, message))
  headeri = ACCESS-KEY, ACCESS-SIGN, ACCESS-PASSPHRASE, ACCESS-TIMESTAMP
Bez vanjskih ovisnosti (stdlib urllib).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from ..config import WEEX_BASE_URL, weex_credentials
from .client import OrderRequest, OrderResult, PaperPosition, WeexClient

_WRITE_TODO = ("Faza 3.2: pisanje (place/cancel/leverage) implementira se nakon "
               "read-only validacije i potvrde tocnih parametara naloga iz WEEX docs.")


class WeexAPIError(RuntimeError):
    pass


class RestWeexClient(WeexClient):
    def __init__(self, api_key: str, api_secret: str, passphrase: str,
                 base_url: str = WEEX_BASE_URL):
        if not api_key or not api_secret or not passphrase:
            raise ValueError("Nedostaju WEEX kljucevi (API key / secret / passphrase).")
        if not base_url:
            raise ValueError("Nedostaje WEEX_BASE_URL.")
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.base_url = base_url.rstrip("/")

    @classmethod
    def from_env(cls) -> "RestWeexClient":
        key, secret, passphrase = weex_credentials()
        return cls(key or "", secret or "", passphrase or "")

    # --- potpis + zahtjev -------------------------------------------------- #
    def _sign(self, timestamp: str, method: str, request_path: str, body: str = "") -> str:
        msg = f"{timestamp}{method.upper()}{request_path}{body}"
        digest = hmac.new(self.api_secret.encode(), msg.encode(), hashlib.sha256).digest()
        return base64.b64encode(digest).decode()

    def _request(self, method: str, path: str, params: dict | None = None,
                 body: dict | None = None, auth: bool = False) -> dict:
        query = urllib.parse.urlencode(params) if params else ""
        request_path = path + (f"?{query}" if query else "")
        url = self.base_url + request_path
        body_str = json.dumps(body) if body else ""

        headers = {"Content-Type": "application/json", "locale": "en-US"}
        if auth:
            ts = str(int(time.time() * 1000))
            sign = self._sign(ts, method, request_path, body_str)
            headers.update({
                "ACCESS-KEY": self.api_key, "ACCESS-SIGN": sign,
                "ACCESS-PASSPHRASE": self.passphrase, "ACCESS-TIMESTAMP": ts,
            })
        req = urllib.request.Request(
            url, data=body_str.encode() if body_str else None,
            headers=headers, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            raise WeexAPIError(f"HTTP {e.code} {method} {path}: {detail}") from None
        except urllib.error.URLError as e:
            raise WeexAPIError(f"Mrezna greska {method} {path}: {e.reason}") from None

    # --- READ-ONLY (Faza 3.1) --------------------------------------------- #
    def server_time(self) -> dict:
        return self._request("GET", "/capi/v2/market/time")

    def exchange_info(self, symbol: str | None = None) -> dict:
        params = {"symbol": symbol} if symbol else None
        return self._request("GET", "/capi/v3/market/exchangeInfo", params=params)

    def ticker(self, symbol: str) -> dict:
        return self._request("GET", "/capi/v2/market/ticker", params={"symbol": symbol})

    def account_assets(self) -> dict:
        return self._request("GET", "/capi/v2/account/assets", auth=True)

    def raw_positions(self) -> dict:
        return self._request("GET", "/capi/v2/account/position/allPosition", auth=True)

    def mark_price(self, symbol: str) -> float | None:
        data = self.ticker(symbol)
        d = data.get("data", data) if isinstance(data, dict) else {}
        if isinstance(d, list) and d:
            d = d[0]
        for k in ("last", "close", "markPrice", "indexPrice", "price"):
            if isinstance(d, dict) and d.get(k) is not None:
                try:
                    return float(d[k])
                except (TypeError, ValueError):
                    pass
        return None

    # --- WRITE (Faza 3.2 - jos ne) ---------------------------------------- #
    def set_leverage(self, symbol: str, leverage: float, margin_mode: str = "isolated") -> None:
        raise NotImplementedError(_WRITE_TODO)

    def place_order(self, req: OrderRequest) -> OrderResult:
        raise NotImplementedError(_WRITE_TODO)

    def cancel_order(self, client_order_id: str) -> OrderResult:
        raise NotImplementedError(_WRITE_TODO)

    def open_orders(self, symbol: str | None = None) -> list[OrderResult]:
        raise NotImplementedError(_WRITE_TODO)

    def positions(self) -> list[PaperPosition]:
        raise NotImplementedError("Koristi raw_positions() za read-only; tipizirano u Fazi 3.2.")
