"""SQLite persistencija (Faza 2) - Repository nad signalima, nalozima, pozicijama.

Koristi samo stdlib sqlite3 (bez vanjskih ovisnosti). Sve vrijeme je UTC ISO-8601.
Idempotentnost: signals.message_id i orders.client_order_id su UNIQUE.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from .models import Signal, TradeStatus
from .paper_broker import PaperOrder
from .risk import PositionPlan

SCHEMA = """
CREATE TABLE IF NOT EXISTS account (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    balance REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id  TEXT UNIQUE NOT NULL,
    kind        TEXT NOT NULL,
    pair        TEXT,
    side        TEXT,
    entry       REAL,
    entry_low   REAL,
    entry_high  REAL,
    stop        REAL,
    take_profit REAL,
    leverage    REAL,
    timeframe   TEXT,
    status      TEXT NOT NULL,
    confidence  REAL,
    raw_text    TEXT,
    notes       TEXT,
    msg_date    TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id   INTEGER NOT NULL REFERENCES signals(id),
    symbol      TEXT NOT NULL,
    side        TEXT NOT NULL,
    entry_price REAL NOT NULL,
    quantity    REAL NOT NULL,
    leverage    REAL,
    stop        REAL,
    take_profit REAL,
    notional    REAL,
    margin      REAL,
    risk_usdt   REAL,
    status      TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id       INTEGER NOT NULL REFERENCES signals(id),
    client_order_id TEXT UNIQUE NOT NULL,
    symbol          TEXT NOT NULL,
    otype           TEXT NOT NULL,
    side            TEXT NOT NULL,
    price           REAL,
    quantity        REAL,
    reduce_only     INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT NOT NULL,
    event      TEXT NOT NULL,
    message_id TEXT,
    detail     TEXT
);

-- Zatvoreni trejdovi (ledger za izvjestaje/dashboard)
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,
    side        TEXT,
    quantity    REAL,
    entry_price REAL,
    exit_price  REAL,
    pnl         REAL NOT NULL,
    opened_at   TEXT,
    closed_at   TEXT NOT NULL,
    source      TEXT
);

-- Trade Manager (Brandon multi-message korelacija)
-- Kljuc je (pair, tag) jer Brandon zna drzati vise pozicija po paru (CORE/SCALP).
CREATE TABLE IF NOT EXISTS tm_positions (
    pair          TEXT NOT NULL,
    tag           TEXT NOT NULL DEFAULT 'SCALP',
    side          TEXT,
    entry         REAL,
    entry_low     REAL,
    entry_high    REAL,
    stop          REAL,
    targets       TEXT,
    open_msg      TEXT,
    status        TEXT,
    remaining_pct INTEGER,
    updated_at    TEXT NOT NULL,
    PRIMARY KEY (pair, tag)
);

CREATE TABLE IF NOT EXISTS tm_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT,
    kind       TEXT NOT NULL,
    pair       TEXT,
    detail     TEXT,
    confidence REAL,
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: str = ":memory:", starting_balance: float = 100.0):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self._ensure_account(starting_balance)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # --- account ---------------------------------------------------------- #
    def _ensure_account(self, balance: float) -> None:
        row = self.conn.execute("SELECT id FROM account WHERE id = 1").fetchone()
        if row is None:
            self.conn.execute("INSERT INTO account (id, balance) VALUES (1, ?)", (balance,))

    def balance(self) -> float:
        return self.conn.execute("SELECT balance FROM account WHERE id = 1").fetchone()["balance"]

    # --- signals ---------------------------------------------------------- #
    def signal_exists(self, message_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM signals WHERE message_id = ?", (message_id,)
        ).fetchone()
        return row is not None

    def insert_signal(self, message_id: str, sig: Signal, msg_date: str | None = None) -> int:
        zone = sig.entry_zone or (None, None)
        tp = sig.take_profits[0].price if sig.take_profits else None
        cur = self.conn.execute(
            """INSERT INTO signals
               (message_id, kind, pair, side, entry, entry_low, entry_high, stop,
                take_profit, leverage, timeframe, status, confidence, raw_text,
                notes, msg_date, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (message_id, sig.kind.value, sig.pair,
             sig.side.value if sig.side else None,
             sig.entry, zone[0], zone[1], sig.stop, tp, sig.leverage,
             sig.timeframe, sig.status.value, sig.confidence, sig.raw_text,
             json.dumps(sig.notes, ensure_ascii=False), msg_date, _now()),
        )
        self.conn.commit()
        return cur.lastrowid

    def update_signal_status(self, signal_id: int, status: TradeStatus, note: str = "") -> None:
        self.conn.execute(
            "UPDATE signals SET status = ? WHERE id = ?", (status.value, signal_id)
        )
        self.conn.commit()

    # --- positions -------------------------------------------------------- #
    def insert_position(self, signal_id: int, sig: Signal, plan: PositionPlan,
                        symbol: str, status: str = "PLANNED") -> int:
        tp = sig.take_profits[0].price if sig.take_profits else None
        cur = self.conn.execute(
            """INSERT INTO positions
               (signal_id, symbol, side, entry_price, quantity, leverage, stop,
                take_profit, notional, margin, risk_usdt, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (signal_id, symbol, sig.side.value, sig.entry, plan.quantity, sig.leverage,
             sig.stop, tp, plan.notional, plan.margin, plan.risk_usdt, status, _now()),
        )
        self.conn.commit()
        return cur.lastrowid

    # --- orders ----------------------------------------------------------- #
    def insert_order(self, signal_id: int, order: PaperOrder, status: str = "NEW") -> int:
        cur = self.conn.execute(
            """INSERT INTO orders
               (signal_id, client_order_id, symbol, otype, side, price, quantity,
                reduce_only, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (signal_id, order.client_order_id, order.symbol, order.otype, order.side,
             order.price, order.quantity, int(order.reduce_only), status, _now()),
        )
        self.conn.commit()
        return cur.lastrowid

    # --- audit ------------------------------------------------------------ #
    def audit(self, event: str, message_id: str | None = None, detail: dict | None = None) -> None:
        self.conn.execute(
            "INSERT INTO audit_log (ts, event, message_id, detail) VALUES (?,?,?,?)",
            (_now(), event, message_id, json.dumps(detail or {}, ensure_ascii=False)),
        )
        self.conn.commit()

    # --- reporting -------------------------------------------------------- #
    def count(self, table: str) -> int:
        return self.conn.execute(f"SELECT COUNT(*) c FROM {table}").fetchone()["c"]

    def positions(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM positions ORDER BY id"
        ).fetchall()

    def total_reserved_margin(self) -> float:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(margin), 0) m FROM positions WHERE status = 'PLANNED'"
        ).fetchone()
        return row["m"]

    def signal_kind_counts(self) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT kind, COUNT(*) c FROM signals GROUP BY kind"
        ).fetchall()
        return {r["kind"]: r["c"] for r in rows}

    def count_planned_positions(self) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) c FROM positions WHERE status = 'PLANNED'"
        ).fetchone()["c"]

    # --- Trade Manager ---------------------------------------------------- #
    def tm_insert_action(self, message_id: str, kind: str, pair: str | None,
                         detail: dict, confidence: float) -> int:
        cur = self.conn.execute(
            """INSERT INTO tm_actions (message_id, kind, pair, detail, confidence, created_at)
               VALUES (?,?,?,?,?,?)""",
            (message_id, kind, pair, json.dumps(detail, ensure_ascii=False),
             confidence, _now()),
        )
        self.conn.commit()
        return cur.lastrowid

    def tm_upsert_position(self, pair: str, tag: str, side: str | None, entry: float | None,
                           entry_zone, stop: float | None, targets: list,
                           open_msg: str | None, status: str, remaining_pct: int) -> None:
        lo, hi = (entry_zone or (None, None))
        self.conn.execute(
            """INSERT INTO tm_positions
               (pair, tag, side, entry, entry_low, entry_high, stop, targets, open_msg,
                status, remaining_pct, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(pair, tag) DO UPDATE SET
                 side=excluded.side, entry=excluded.entry, entry_low=excluded.entry_low,
                 entry_high=excluded.entry_high, stop=excluded.stop,
                 targets=excluded.targets, open_msg=excluded.open_msg,
                 status=excluded.status, remaining_pct=excluded.remaining_pct,
                 updated_at=excluded.updated_at""",
            (pair, tag, side, entry, lo, hi, stop,
             json.dumps(targets, ensure_ascii=False), open_msg, status,
             remaining_pct, _now()),
        )
        self.conn.commit()

    def tm_positions(self) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM tm_positions ORDER BY pair").fetchall()

    def tm_action_counts(self) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT kind, COUNT(*) c FROM tm_actions GROUP BY kind"
        ).fetchall()
        return {r["kind"]: r["c"] for r in rows}

    # --- trades ledger (izvjestaji) -------------------------------------- #
    def record_trade(self, symbol: str, side: str | None, quantity: float | None,
                     entry_price: float | None, exit_price: float | None, pnl: float,
                     closed_at: str | None = None, opened_at: str | None = None,
                     source: str = "") -> int:
        cur = self.conn.execute(
            """INSERT INTO trades
               (symbol, side, quantity, entry_price, exit_price, pnl,
                opened_at, closed_at, source)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (symbol, side, quantity, entry_price, exit_price, pnl,
             opened_at, closed_at or _now(), source),
        )
        self.conn.commit()
        return cur.lastrowid

    def trades(self) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM trades ORDER BY closed_at").fetchall()

    def clear_trades(self) -> None:
        self.conn.execute("DELETE FROM trades")
        self.conn.commit()
