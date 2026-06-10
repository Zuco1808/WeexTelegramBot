# -*- coding: utf-8 -*-
"""Izvjestaji / dashboard nad trades ledgerom (dnevni / sedmicni / mjesecni).

Zeleno = dan/period u plusu (PnL + broj trejdova), crveno = u minusu.
Dodatni izvjestaji: ukupni sazetak, win rate, po simbolu, najbolji/najgori,
streakovi i equity sparkline. Ne ovisi o vanjskim paketima.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

# ANSI boje (rade u modernom Windows Terminalu/PowerShellu)
GREEN, RED, GREY, BOLD, RESET = "\033[92m", "\033[91m", "\033[90m", "\033[1m", "\033[0m"
_SPARK = "▁▂▃▄▅▆▇█"


@dataclass
class Trade:
    symbol: str
    side: str | None
    pnl: float
    closed_at: datetime
    source: str = ""


# --------------------------------------------------------------------------- #
def _parse_dt(s: str) -> datetime:
    s = (s or "").strip()
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d.%m.%Y %H:%M:%S"):
            try:
                return datetime.strptime(s[:19], fmt)
            except ValueError:
                continue
    return datetime.min


def trades_from_rows(rows) -> list[Trade]:
    out = []
    for r in rows:
        out.append(Trade(r["symbol"], r["side"], float(r["pnl"]),
                         _parse_dt(r["closed_at"]), r["source"] or ""))
    return out


def _period_key(dt: datetime, period: str) -> str:
    if period == "day":
        return dt.strftime("%Y-%m-%d")
    if period == "week":
        y, w, _ = dt.isocalendar()
        return f"{y}-W{w:02d}"
    if period == "month":
        return dt.strftime("%Y-%m")
    raise ValueError(period)


@dataclass
class Bucket:
    key: str
    pnl: float
    count: int
    wins: int

    @property
    def winrate(self) -> float:
        return (self.wins / self.count * 100) if self.count else 0.0


def aggregate(trades: list[Trade], period: str) -> list[Bucket]:
    acc: dict[str, list[float]] = {}
    for t in trades:
        k = _period_key(t.closed_at, period)
        b = acc.setdefault(k, [0.0, 0, 0])
        b[0] += t.pnl
        b[1] += 1
        b[2] += 1 if t.pnl > 0 else 0
    return [Bucket(k, v[0], int(v[1]), int(v[2])) for k, v in sorted(acc.items())]


# --------------------------------------------------------------------------- #
def _fmt_pnl(x: float) -> str:
    return f"{x:+.2f} USDT"


def _color(text: str, pnl: float, on: bool) -> str:
    if not on:
        return text
    c = GREEN if pnl > 0 else RED if pnl < 0 else GREY
    return f"{c}{text}{RESET}"


def _dot(pnl: float) -> str:
    return "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"


def render_period(trades: list[Trade], period: str, color: bool = True) -> str:
    label = {"day": "DNEVNI", "week": "SEDMICNI", "month": "MJESECNI"}[period]
    lines = [f"{BOLD}=== {label} IZVJESTAJ ==={RESET}" if color else f"=== {label} IZVJESTAJ ==="]
    buckets = aggregate(trades, period)
    for b in buckets:
        row = (f"{_dot(b.pnl)} {b.key:<11} {_fmt_pnl(b.pnl):>16}   "
               f"trejdova: {b.count:<3}  (win {b.winrate:.0f}%)")
        lines.append(_color(row, b.pnl, color))
    if not buckets:
        lines.append("  (nema trejdova)")
    return "\n".join(lines)


def equity_sparkline(trades: list[Trade]) -> str:
    daily = aggregate(trades, "day")
    if not daily:
        return ""
    cum, running = [], 0.0
    for b in daily:
        running += b.pnl
        cum.append(running)
    lo, hi = min(cum), max(cum)
    rng = (hi - lo) or 1.0
    spark = "".join(_SPARK[min(7, int((v - lo) / rng * 7))] for v in cum)
    return f"Equity (kumulativni PnL): {spark}  ({_fmt_pnl(running)})"


def by_symbol(trades: list[Trade]) -> list[Bucket]:
    acc: dict[str, list[float]] = {}
    for t in trades:
        b = acc.setdefault(t.symbol, [0.0, 0, 0])
        b[0] += t.pnl
        b[1] += 1
        b[2] += 1 if t.pnl > 0 else 0
    out = [Bucket(k, v[0], int(v[1]), int(v[2])) for k, v in acc.items()]
    return sorted(out, key=lambda x: x.pnl, reverse=True)


def summary(trades: list[Trade]) -> dict:
    if not trades:
        return {"total_pnl": 0.0, "count": 0, "winrate": 0.0,
                "avg": 0.0, "best": None, "worst": None}
    pnls = [t.pnl for t in trades]
    wins = sum(1 for p in pnls if p > 0)
    days = aggregate(trades, "day")
    best = max(days, key=lambda b: b.pnl)
    worst = min(days, key=lambda b: b.pnl)
    return {
        "total_pnl": sum(pnls),
        "count": len(trades),
        "winrate": wins / len(trades) * 100,
        "avg": sum(pnls) / len(pnls),
        "best": best, "worst": worst,
    }


def render_dashboard(trades: list[Trade], color: bool = True) -> str:
    parts = []
    s = summary(trades)
    head = (f"{BOLD}PnL ukupno: {_fmt_pnl(s['total_pnl'])}{RESET}  |  "
            f"trejdova: {s['count']}  |  win: {s['winrate']:.0f}%  |  "
            f"prosjek/trejd: {_fmt_pnl(s['avg'])}") if color else (
            f"PnL ukupno: {_fmt_pnl(s['total_pnl'])}  |  trejdova: {s['count']}  |  "
            f"win: {s['winrate']:.0f}%  |  prosjek/trejd: {_fmt_pnl(s['avg'])}")
    parts.append(_color(head, s["total_pnl"], color))
    if s["best"]:
        parts.append(f"  najbolji dan: {s['best'].key} ({_fmt_pnl(s['best'].pnl)}, "
                     f"{s['best'].count} trejdova)")
        parts.append(f"  najgori dan:  {s['worst'].key} ({_fmt_pnl(s['worst'].pnl)}, "
                     f"{s['worst'].count} trejdova)")
    sp = equity_sparkline(trades)
    if sp:
        parts.append("  " + sp)
    parts.append("")
    for period in ("day", "week", "month"):
        parts.append(render_period(trades, period, color))
        parts.append("")
    parts.append(f"{BOLD}=== PO SIMBOLU ==={RESET}" if color else "=== PO SIMBOLU ===")
    for b in by_symbol(trades):
        row = f"{_dot(b.pnl)} {b.key:<10} {_fmt_pnl(b.pnl):>16}   trejdova: {b.count:<3}  (win {b.winrate:.0f}%)"
        parts.append(_color(row, b.pnl, color))
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
def equity_svg(trades: list[Trade], width: int = 820, height: int = 260) -> str:
    """Inline SVG linijski grafikon kumulativnog PnL-a po danima."""
    days = aggregate(trades, "day")
    if not days:
        return ""
    cum, running = [], 0.0
    for b in days:
        running += b.pnl
        cum.append(running)

    pad_l, pad_r, pad_t, pad_b = 52, 18, 18, 28
    plot_w, plot_h = width - pad_l - pad_r, height - pad_t - pad_b
    y_min, y_max = min(min(cum), 0.0), max(max(cum), 0.0)
    y_rng = (y_max - y_min) or 1.0
    n = len(cum)

    def X(i: int) -> float:
        return pad_l + (i / (n - 1) * plot_w if n > 1 else plot_w / 2)

    def Y(v: float) -> float:
        return pad_t + (1 - (v - y_min) / y_rng) * plot_h

    pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(cum))
    color = "#16a34a" if running >= 0 else "#dc2626"
    y0 = Y(0.0)
    area = (f"M {X(0):.1f},{y0:.1f} L "
            + " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(cum))
            + f" L {X(n - 1):.1f},{y0:.1f} Z")

    def lbl(v: float, y: float) -> str:
        return (f'<text x="{pad_l - 8}" y="{y + 4:.1f}" text-anchor="end" '
                f'font-size="11" fill="#666">{v:+.0f}</text>')

    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="Equity curve">'
        f'<rect x="{pad_l}" y="{pad_t}" width="{plot_w}" height="{plot_h}" '
        f'fill="#fafafa" stroke="#eee"/>'
        f'<line x1="{pad_l}" y1="{y0:.1f}" x2="{pad_l + plot_w}" y2="{y0:.1f}" '
        f'stroke="#bbb" stroke-dasharray="4 3"/>'
        f'<path d="{area}" fill="{color}" fill-opacity="0.12"/>'
        f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/>'
        f'{lbl(y_max, Y(y_max))}{lbl(0, y0)}{lbl(y_min, Y(y_min))}'
        f'<text x="{pad_l}" y="{height - 8}" font-size="11" fill="#666">{days[0].key}</text>'
        f'<text x="{pad_l + plot_w}" y="{height - 8}" text-anchor="end" '
        f'font-size="11" fill="#666">{days[-1].key}</text>'
        f'</svg>'
    )


def to_html(trades: list[Trade]) -> str:
    s = summary(trades)

    def cell(pnl: float) -> str:
        bg = "#16a34a" if pnl > 0 else "#dc2626" if pnl < 0 else "#6b7280"
        return f'style="background:{bg};color:#fff;padding:4px 8px;border-radius:4px"'

    def table(title: str, buckets: list[Bucket]) -> str:
        rows = "".join(
            f"<tr><td>{b.key}</td><td {cell(b.pnl)}>{_fmt_pnl(b.pnl)}</td>"
            f"<td>{b.count}</td><td>{b.winrate:.0f}%</td></tr>" for b in buckets)
        return (f"<h2>{title}</h2><table cellspacing=6>"
                f"<tr><th>Period</th><th>PnL</th><th>Trejdova</th><th>Win</th></tr>{rows}</table>")

    body = (f"<h1>WEEX Bot — Izvjestaj</h1>"
            f"<p><b>PnL ukupno:</b> {_fmt_pnl(s['total_pnl'])} &nbsp; "
            f"<b>Trejdova:</b> {s['count']} &nbsp; <b>Win:</b> {s['winrate']:.0f}%</p>"
            + (f"<h2>Equity curve</h2>{equity_svg(trades)}" if trades else "")
            + table("Dnevni", aggregate(trades, "day"))
            + table("Sedmicni", aggregate(trades, "week"))
            + table("Mjesecni", aggregate(trades, "month"))
            + table("Po simbolu", by_symbol(trades)))
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<style>body{{font-family:system-ui;margin:24px}}"
            f"table{{border-collapse:separate;margin-bottom:24px}}"
            f"th{{text-align:left;color:#555}}</style></head><body>{body}</body></html>")
