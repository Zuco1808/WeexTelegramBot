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


class WeexAPIError(RuntimeError):
    pass


def _find_contract(data, needle: str) -> dict:
    """Rekurzivno nadi contract dict (ima vise polja i sadrzi 'needle' u vrijednosti)."""
    best: dict = {}
    stack = [data]
    while stack:
        obj = stack.pop()
        if isinstance(obj, dict):
            if len(obj) > 2 and any(isinstance(v, str) and needle in v.lower()
                                    for v in obj.values()):
                if len(obj) > len(best):
                    best = obj
            stack.extend(obj.values())
        elif isinstance(obj, list):
            stack.extend(obj)
    return best


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
        self._spec_cache: dict[str, dict] = {}

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

    # --- simboli --------------------------------------------------------- #
    @staticmethod
    def _v2_symbol(symbol: str) -> str:
        """Kanonski 'BTCUSDT' -> WEEX v2 contract format 'cmt_btcusdt'."""
        s = (symbol or "").strip()
        return s if s.lower().startswith("cmt_") else "cmt_" + s.lower()

    # --- READ-ONLY (Faza 3.1) --------------------------------------------- #
    def server_time(self) -> dict:
        return self._request("GET", "/capi/v2/market/time")

    def exchange_info(self, symbol: str | None = None) -> dict:
        params = {"symbol": symbol} if symbol else None
        return self._request("GET", "/capi/v3/market/exchangeInfo", params=params)

    def ticker(self, symbol: str) -> dict:
        return self._request("GET", "/capi/v2/market/ticker",
                             params={"symbol": self._v2_symbol(symbol)})

    def tickers(self) -> dict:
        return self._request("GET", "/capi/v2/market/tickers")

    def account_assets(self) -> dict:
        return self._request("GET", "/capi/v2/account/assets", auth=True)

    def raw_positions(self) -> dict:
        return self._request("GET", "/capi/v2/account/position/allPosition", auth=True)

    def raw_open_orders(self, symbol: str | None = None) -> dict:
        params = {"symbol": self._v2_symbol(symbol)} if symbol else None
        return self._request("GET", "/capi/v2/order/current", params=params, auth=True)

    def account_balance(self, coin: str = "USDT") -> float:
        data = self.account_assets()
        rows = data.get("data", data) if isinstance(data, dict) else data
        rows = rows if isinstance(rows, list) else []
        for r in rows:
            if str(r.get("coinName") or r.get("coin") or "").upper() == coin:
                try:
                    return float(r.get("available") or 0)
                except (TypeError, ValueError):
                    return 0.0
        return 0.0

    def symbol_spec(self, symbol: str) -> dict:
        """Normalizirani contract parametri (cache po simbolu)."""
        key = symbol.upper()
        if key in self._spec_cache:
            return self._spec_cache[key]
        base = key[:-4].lower() if key.endswith("USDT") else key.lower()
        c = _find_contract(self.exchange_info(symbol), base + "usdt")
        spec = {
            "pricePrecision": int(c.get("pricePrecision", 2)),
            "quantityPrecision": int(c.get("quantityPrecision", 3)),
            "minOrderSize": float(c.get("minOrderSize", 0) or 0),
            "maxOrderSize": float(c.get("maxOrderSize", 0) or 0),
            "contractVal": float(c.get("contractVal", 0) or 0),
            "buyLimitPriceRatio": float(c.get("buyLimitPriceRatio", 0.01) or 0.01),
            "sellLimitPriceRatio": float(c.get("sellLimitPriceRatio", 0.01) or 0.01),
        }
        self._spec_cache[key] = spec
        return spec

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

    # --- WRITE (Faza 3.2) ------------------------------------------------- #
    # type: open long / open short / close long (sell reduce) / close short (buy reduce)
    _TYPE = {("BUY", False): "1", ("SELL", False): "2",
             ("SELL", True): "3", ("BUY", True): "4"}

    @staticmethod
    def _fmt(x) -> str:
        if isinstance(x, float):
            return f"{x:.10f}".rstrip("0").rstrip(".")
        return str(x)

    @staticmethod
    def _clean_oid(oid: str) -> str:
        return "".join(ch for ch in (oid or "") if ch.isalnum())[:40]

    def _leverage_body(self, symbol: str, leverage: float, margin_mode: str) -> dict:
        mm = 3 if margin_mode == "isolated" else 1
        return {"symbol": self._v2_symbol(symbol), "marginMode": mm,
                "longLeverage": str(int(leverage)), "shortLeverage": str(int(leverage))}

    def _order_body(self, req: OrderRequest) -> dict:
        body = {
            "symbol": self._v2_symbol(req.symbol),
            "client_oid": self._clean_oid(req.client_order_id or f"wx{int(time.time()*1000)}"),
            "size": self._fmt(req.quantity),
            "type": self._TYPE[(req.side, req.reduce_only)],
            "order_type": "0",                       # normal
            "match_price": "1" if req.otype == "MARKET" else "0",
            "marginMode": 3,                         # isolated
        }
        if body["match_price"] == "0":
            body["price"] = self._fmt(req.price)
        if req.preset_sl is not None:
            body["presetStopLossPrice"] = self._fmt(req.preset_sl)
        if req.preset_tp is not None:
            body["presetTakeProfitPrice"] = self._fmt(req.preset_tp)
        return body

    def set_leverage(self, symbol: str, leverage: float, margin_mode: str = "isolated") -> dict:
        return self._request("POST", "/capi/v2/account/leverage",
                             body=self._leverage_body(symbol, leverage, margin_mode), auth=True)

    def place_order(self, req: OrderRequest) -> OrderResult:
        resp = self._request("POST", "/capi/v2/order/placeOrder",
                             body=self._order_body(req), auth=True)
        data = resp.get("data", {}) if isinstance(resp, dict) else {}
        oid = data.get("orderId") or data.get("order_id") if isinstance(data, dict) else None
        coid = self._clean_oid(req.client_order_id or "")
        return OrderResult(client_order_id=coid, status="SUBMITTED",
                           filled_price=None, message=json.dumps(resp, ensure_ascii=False))

    def cancel_order(self, client_order_id: str, symbol: str | None = None) -> OrderResult:
        body: dict = {"clientOid": self._clean_oid(client_order_id)}
        if symbol:
            body["symbol"] = self._v2_symbol(symbol)
        resp = self._request("POST", "/capi/v2/order/cancel_order", body=body, auth=True)
        return OrderResult(client_order_id=client_order_id, status="CANCEL_SENT",
                           message=json.dumps(resp, ensure_ascii=False))

    def open_orders(self, symbol: str | None = None) -> list[OrderResult]:
        resp = self.raw_open_orders(symbol)
        rows = resp.get("data", resp) if isinstance(resp, dict) else resp
        rows = rows if isinstance(rows, list) else []
        out = []
        for r in rows:
            out.append(OrderResult(
                client_order_id=str(r.get("client_oid") or r.get("clientOid") or ""),
                status=str(r.get("status", "")), message=json.dumps(r, ensure_ascii=False)))
        return out

    def positions(self) -> list[PaperPosition]:
        resp = self.raw_positions()
        rows = resp.get("data", resp) if isinstance(resp, dict) else resp
        rows = rows if isinstance(rows, list) else []
        out = []
        for r in rows:
            try:
                qty = float(r.get("size") or r.get("total") or 0)
            except (TypeError, ValueError):
                qty = 0.0
            out.append(PaperPosition(
                symbol=str(r.get("symbol", "")),
                side="LONG" if str(r.get("side", "")).lower() in ("long", "1") else "SHORT",
                quantity=qty, entry_price=float(r.get("averageOpenPrice") or 0) or 0.0,
                leverage=float(r.get("leverage") or 0) or None))
        return out
